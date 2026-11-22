"""Reserva, liquidación y reconciliación del presupuesto externo (Entrega 2)."""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import Case, Conversation, ProviderBudgetLedger, Run
from secguard_advisor.evidence.budget import (
    BudgetExceeded,
    begin_call,
    reconcile_call,
    reconcile_startup,
    release_call,
    settle_call,
)

AT = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)


def _settings(tmp_path: Path, **overrides) -> Settings:
    values = {
        "storage_dir": tmp_path / "storage",
        "generation_provider": "deepseek",
        "deepseek_api_key": "secret",
        "external_budget_usd": Decimal("0.002"),
        "external_run_budget_usd": Decimal("0.001"),
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def _factory(tmp_path: Path, settings: Settings):
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    return create_session_factory(engine)


def _run(factory, *, status: str = "running") -> str:
    with factory() as session:
        case = Case(title="Caso de presupuesto", synthetic_notice="Escenario sintético.")
        session.add(case)
        session.flush()
        conversation = Conversation(case_id=case.id, thread_id=f"thread-{case.id}")
        session.add(conversation)
        session.flush()
        run = Run(
            case_id=case.id,
            conversation_id=conversation.id,
            status=status,
            generator_model="deepseek-flash",
            generator_num_ctx=8192,
            generator_temperature=0.1,
            embedding_model="embeddinggemma",
            embedding_dim=768,
            prompt_version="chat-v8",
        )
        session.add(run)
        session.commit()
        return run.id


def _reserve(factory, settings, run_id: str):
    with factory() as session:
        reservation = begin_call(
            session,
            settings=settings,
            run_id=run_id,
            attempt_no=1,
            provider="deepseek",
            model="deepseek-flash",
            input_tokens=1000,
            max_output_tokens=1200,
            at=AT,
        )
        session.commit()
        return reservation


def test_zero_budget_blocks_before_any_call(tmp_path: Path) -> None:
    settings = _settings(
        tmp_path, external_budget_usd=Decimal("0"), external_run_budget_usd=Decimal("0")
    )
    factory = _factory(tmp_path, settings)
    run_id = _run(factory)

    with pytest.raises(BudgetExceeded):
        _reserve(factory, settings, run_id)


def test_global_and_run_budgets_block_independently(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    factory = _factory(tmp_path, settings)
    run_id = _run(factory)
    _reserve(factory, settings, run_id)

    with pytest.raises(BudgetExceeded, match="turno"):
        _reserve(factory, settings, run_id)


def test_settle_uses_observed_cost(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    factory = _factory(tmp_path, settings)
    run_id = _run(factory)
    reservation = _reserve(factory, settings, run_id)

    with factory() as session:
        result = settle_call(
            session,
            reservation,
            provider="deepseek",
            model="deepseek-flash",
            input_tokens=1000,
            output_tokens=500,
            cached_tokens=200,
            cache_write_tokens=0,
            tariff_version=settings.external_tariff_version,
            at=AT,
        )
        entry = session.get(ProviderBudgetLedger, reservation.id)

    assert result.status == "calculated"
    assert entry.state == "settled"
    assert entry.settled_usd == result.usd


def test_unknown_usage_keeps_the_reservation(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    factory = _factory(tmp_path, settings)
    run_id = _run(factory)
    reservation = _reserve(factory, settings, run_id)

    with factory() as session:
        result = settle_call(
            session,
            reservation,
            provider="deepseek",
            model="deepseek-flash",
            input_tokens=None,
            output_tokens=None,
            cached_tokens=None,
            cache_write_tokens=None,
            tariff_version=settings.external_tariff_version,
            at=AT,
        )
        entry = session.get(ProviderBudgetLedger, reservation.id)

    assert result.status == "unknown"
    assert entry.state == "reconciled"
    assert entry.settled_usd == entry.reserved_usd


def test_uncertain_error_keeps_the_reservation(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    factory = _factory(tmp_path, settings)
    run_id = _run(factory)
    reservation = _reserve(factory, settings, run_id)

    with factory() as session:
        reconcile_call(session, reservation)
        entry = session.get(ProviderBudgetLedger, reservation.id)

    assert entry.state == "reconciled"
    assert entry.settled_usd == entry.reserved_usd


def test_release_only_for_known_not_sent(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    factory = _factory(tmp_path, settings)
    run_id = _run(factory)
    reservation = _reserve(factory, settings, run_id)

    with factory() as session:
        release_call(session, reservation)
        entry = session.get(ProviderBudgetLedger, reservation.id)

    assert entry.state == "released"
    assert entry.settled_usd == Decimal("0")


def test_startup_reconciles_terminal_runs(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    factory = _factory(tmp_path, settings)
    run_id = _run(factory, status="succeeded")
    reservation = _reserve(factory, settings, run_id)

    with factory() as session:
        assert reconcile_startup(session) == 1
        session.commit()
        entry = session.get(ProviderBudgetLedger, reservation.id)

    assert entry.state == "reconciled"
    assert entry.settled_usd == entry.reserved_usd
