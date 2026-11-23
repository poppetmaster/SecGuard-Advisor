"""Telemetría por solicitud de los generadores de IA."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select
from tests.fixtures.conversation import build_env

from secguard_advisor.ai_usage.telemetry import set_evaluation_context
from secguard_advisor.config import Settings
from secguard_advisor.conversation.llm import ModelTimeout, ModelUnavailable
from secguard_advisor.conversation.providers.usage import provider_call
from secguard_advisor.db.models import (
    AiRequest,
    Case,
    Conversation,
    ProviderBudgetLedger,
    Run,
)

SECRET = "sk-telemetry-secret"


@dataclass
class _Deps:
    settings: Settings
    generator: object


@dataclass
class _Context:
    factory: object
    run_id: str
    attempt_no: int
    deps: _Deps


class _Generator:
    def __init__(self, *, provider: str, model: str, identity: str | None = None) -> None:
        self.provider = provider
        self.model = model
        self.identity = identity
        self.last_usage: dict | None = None


def _settings(tmp_path: Path, **overrides) -> Settings:
    values = {
        "storage_dir": tmp_path / "storage",
        "generation_provider": "deepseek",
        "generation_model": "deepseek-flash",
        "generation_max_output_tokens": 512,
        "deepseek_api_key": SECRET,
        "external_budget_usd": Decimal("5"),
        "external_run_budget_usd": Decimal("5"),
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def _run(env, settings: Settings, *, attempt_no: int = 1, retry_of: str | None = None) -> str:
    with env.factory() as session:
        case = Case(title="Caso de telemetría", synthetic_notice="Escenario sintético.")
        session.add(case)
        session.flush()
        conversation = Conversation(case_id=case.id, thread_id=f"thread-{case.id}")
        session.add(conversation)
        session.flush()
        run = Run(
            case_id=case.id,
            conversation_id=conversation.id,
            status="running",
            attempt_no=attempt_no,
            retry_of_run_id=retry_of,
            generator_provider=settings.generation_provider,
            generator_model=settings.provider_model,
            generator_num_ctx=8192,
            generator_temperature=0.1,
            embedding_model="embeddinggemma",
            embedding_dim=768,
            prompt_version="chat-v8",
        )
        session.add(run)
        session.commit()
        return run.id


def _call(
    env,
    settings: Settings,
    generator: _Generator,
    run_id: str,
    *,
    operation="generate",
    error: Exception | None = None,
):
    context = _Context(
        factory=env.factory,
        run_id=run_id,
        attempt_no=1,
        deps=_Deps(settings=settings, generator=generator),
    )
    with provider_call(context, operation=operation, admitted_tokens=1000):
        if error is not None:
            raise error
        return None


def _rows(env) -> list[AiRequest]:
    with env.factory() as session:
        return list(session.scalars(select(AiRequest).order_by(AiRequest.started_at)))


def test_local_call_records_tokens_without_api_cost(tmp_path: Path) -> None:
    env = build_env(tmp_path)
    settings = _settings(tmp_path, generation_provider="ollama", generation_model="qwen3.5:9b")
    run_id = _run(env, settings)
    generator = _Generator(provider="ollama", model="qwen3.5:9b", identity="digest-local")
    generator.last_usage = {
        "input_tokens": 120,
        "output_tokens": 30,
        "cached_tokens": 0,
        "source": "observed",
    }

    _call(env, settings, generator, run_id)

    (row,) = _rows(env)
    assert row.provider == "ollama"
    assert row.status == "completed"
    assert row.input_tokens == 120
    assert row.output_tokens == 30
    assert row.cost_status == "not_applicable"
    assert row.cost_usd is None
    assert row.currency == "USD"
    assert row.usage_source == "observed"


def test_external_call_records_cache_cost_and_tariff(tmp_path: Path) -> None:
    env = build_env(tmp_path)
    settings = _settings(tmp_path)
    run_id = _run(env, settings)
    generator = _Generator(provider="deepseek", model="deepseek-flash")
    generator.last_usage = {
        "input_tokens": 1000,
        "output_tokens": 100,
        "cached_tokens": 400,
        "cache_write_tokens": 0,
        "source": "observed",
    }

    _call(env, settings, generator, run_id)

    (row,) = _rows(env)
    assert row.cost_status == "calculated"
    assert row.cost_usd is not None and row.cost_usd > 0
    assert row.tariff_version == "2026-11-22"
    assert row.cached_tokens == 400
    assert row.currency == "USD"


def test_timeout_keeps_cost_unknown_and_reservation_committed(tmp_path: Path) -> None:
    env = build_env(tmp_path)
    settings = _settings(tmp_path)
    run_id = _run(env, settings)
    generator = _Generator(provider="deepseek", model="deepseek-flash")

    with pytest.raises(ModelTimeout):
        _call(env, settings, generator, run_id, error=ModelTimeout("timeout"))

    (row,) = _rows(env)
    assert row.status == "timeout"
    assert row.cost_status == "unknown"
    assert row.cost_usd is None
    assert row.usage_source == "unavailable"
    with env.factory() as session:
        ledger = session.scalar(select(ProviderBudgetLedger))
        assert ledger.state == "reconciled"
        assert ledger.settled_usd == ledger.reserved_usd


def test_connection_failure_is_uncertain(tmp_path: Path) -> None:
    env = build_env(tmp_path)
    settings = _settings(tmp_path)
    run_id = _run(env, settings)
    generator = _Generator(provider="deepseek", model="deepseek-flash")

    with pytest.raises(ModelUnavailable):
        _call(env, settings, generator, run_id, error=ModelUnavailable("sin red"))

    (row,) = _rows(env)
    assert row.status == "uncertain"
    assert row.cost_status == "unknown"


def test_reasoning_tokens_are_kept_with_inclusion_flag(tmp_path: Path) -> None:
    env = build_env(tmp_path)
    settings = _settings(tmp_path)
    run_id = _run(env, settings)
    generator = _Generator(provider="deepseek", model="deepseek-flash")
    generator.last_usage = {
        "input_tokens": 10,
        "output_tokens": 5,
        "reasoning_tokens": 3,
        "reasoning_included_in_output": True,
        "source": "observed",
    }

    _call(env, settings, generator, run_id)

    (row,) = _rows(env)
    assert row.reasoning_tokens == 3
    assert row.reasoning_included_in_output is True


def test_one_consultation_can_record_decision_generation_and_repair(tmp_path: Path) -> None:
    env = build_env(tmp_path)
    settings = _settings(tmp_path)
    run_id = _run(env, settings)
    generator = _Generator(provider="deepseek", model="deepseek-flash")
    generator.last_usage = {"input_tokens": 10, "output_tokens": 5, "source": "observed"}

    _call(env, settings, generator, run_id, operation="decide")
    _call(env, settings, generator, run_id, operation="generate")
    _call(env, settings, generator, run_id, operation="repair")

    assert {row.operation for row in _rows(env)} == {"decide", "generate", "repair"}


def test_operation_attempt_is_recorded_once(tmp_path: Path) -> None:
    env = build_env(tmp_path)
    settings = _settings(tmp_path)
    run_id = _run(env, settings)
    generator = _Generator(provider="deepseek", model="deepseek-flash")
    generator.last_usage = {"input_tokens": 10, "output_tokens": 5, "source": "observed"}

    _call(env, settings, generator, run_id, operation="repair")
    _call(env, settings, generator, run_id, operation="repair")

    assert len(_rows(env)) == 1


def test_evaluation_context_is_persisted(tmp_path: Path) -> None:
    env = build_env(tmp_path)
    settings = _settings(tmp_path)
    run_id = _run(env, settings)
    generator = _Generator(provider="deepseek", model="deepseek-flash")
    generator.last_usage = {"input_tokens": 10, "output_tokens": 5, "source": "observed"}

    with set_evaluation_context("eval-test", "S01"):
        _call(env, settings, generator, run_id)

    (row,) = _rows(env)
    assert row.evaluation_id == "eval-test"
    assert row.scenario == "S01"


def test_telemetry_keeps_no_secret_or_prompt(tmp_path: Path) -> None:
    env = build_env(tmp_path)
    settings = _settings(tmp_path)
    run_id = _run(env, settings)
    generator = _Generator(provider="deepseek", model="deepseek-flash")
    generator.last_usage = {"input_tokens": 10, "output_tokens": 5, "source": "observed"}

    _call(env, settings, generator, run_id)

    with env.factory() as session:
        row = session.scalar(select(AiRequest))
        payload = " ".join(str(value) for value in vars(row).values())
    assert SECRET not in payload
    assert "Authorization" not in payload
    assert "pregunta" not in payload


def test_retry_run_links_to_previous_run_without_duplication(tmp_path: Path) -> None:
    env = build_env(tmp_path)
    settings = _settings(tmp_path)
    first = _run(env, settings)
    second = _run(env, settings, attempt_no=2, retry_of=first)
    generator = _Generator(provider="deepseek", model="deepseek-flash")
    generator.last_usage = {"input_tokens": 10, "output_tokens": 5, "source": "observed"}

    _call(env, settings, generator, second)

    with env.factory() as session:
        assert session.scalar(select(func.count()).select_from(AiRequest)) == 1
        retried = session.get(Run, second)
        assert retried.retry_of_run_id == first
        assert retried.attempt_no == 2
