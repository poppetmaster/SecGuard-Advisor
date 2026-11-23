"""Agregados, filtros y comparativo del panel de uso."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from secguard_advisor.ai_usage.evaluations import build_comparison_view
from secguard_advisor.ai_usage.queries import UsageFilterError, UsageFilters, build_usage_view
from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import (
    AiEvaluation,
    AiEvaluationResult,
    AiRequest,
    Case,
    Conversation,
    ProviderBudgetLedger,
    Run,
)


def _factory(tmp_path: Path):
    settings = Settings(_env_file=None, storage_dir=tmp_path / "storage")
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    return create_session_factory(engine)


def _run(
    session,
    *,
    run_id: str,
    provider: str,
    model: str,
    started_at: str,
    duration_ms: int,
    status: str = "succeeded",
    attempt_no: int = 1,
    retry_of: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cost_status: str = "not_applicable",
    cost_usd: Decimal | None = None,
    case_id: str = "case-1",
) -> None:
    if retry_of is not None:
        session.flush()
    if session.get(Case, case_id) is None:
        session.add(Case(id=case_id, title="Caso de uso", synthetic_notice="Sintético."))
        session.flush()
        session.add(Conversation(id=f"conv-{case_id}", case_id=case_id, thread_id="t"))
        session.flush()
    session.add(
        Run(
            id=run_id,
            case_id=case_id,
            conversation_id=f"conv-{case_id}",
            status=status,
            attempt_no=attempt_no,
            retry_of_run_id=retry_of,
            generator_provider=provider,
            generator_model=model,
            generator_num_ctx=8192,
            generator_temperature=0.1,
            embedding_model="embeddinggemma",
            embedding_dim=768,
            prompt_version="chat-v8",
            duration_ms=duration_ms,
            usage_input_tokens=input_tokens,
            usage_output_tokens=output_tokens,
            usage_source="observed" if input_tokens is not None else None,
            cost_status=cost_status,
            cost_usd=cost_usd,
            cost_tariff_version="2026-11-22" if cost_usd is not None else None,
            started_at=started_at,
        )
    )
    session.flush()


def _request(
    session,
    *,
    request_id: str,
    run_id: str,
    operation: str,
    provider: str,
    model: str,
    started_at: str,
    status: str = "completed",
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cached_tokens: int | None = None,
    usage_source: str = "observed",
    cost_status: str = "not_applicable",
    cost_usd: Decimal | None = None,
) -> None:
    session.add(
        AiRequest(
            id=request_id,
            run_id=run_id,
            operation=operation,
            attempt_no=1,
            provider=provider,
            model=model,
            started_at=started_at,
            finished_at=started_at,
            status=status,
            duration_ms=100,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            usage_source=usage_source,
            cost_status=cost_status,
            cost_usd=cost_usd,
            currency="USD",
            tariff_version="2026-11-22" if cost_usd is not None else None,
        )
    )
    session.flush()


def _seed(factory) -> None:
    with factory() as session:
        _run(
            session,
            run_id="run-1",
            provider="deepseek",
            model="deepseek-flash",
            started_at="2026-01-15T15:00:00+00:00",
            duration_ms=1000,
            input_tokens=100,
            output_tokens=20,
            cost_status="calculated",
            cost_usd=Decimal("0.001"),
        )
        _request(
            session,
            request_id="req-1",
            run_id="run-1",
            operation="decide",
            provider="deepseek",
            model="deepseek-flash",
            started_at="2026-01-15T15:00:01+00:00",
            input_tokens=60,
            output_tokens=10,
            cached_tokens=20,
            cost_status="calculated",
            cost_usd=Decimal("0.0004"),
        )
        _request(
            session,
            request_id="req-2",
            run_id="run-1",
            operation="generate",
            provider="deepseek",
            model="deepseek-flash",
            started_at="2026-01-15T15:00:02+00:00",
            input_tokens=40,
            output_tokens=10,
            cost_status="calculated",
            cost_usd=Decimal("0.0006"),
        )
        _run(
            session,
            run_id="run-2",
            provider="ollama",
            model="qwen3.5:9b",
            started_at="2026-01-15T16:00:00+00:00",
            duration_ms=3000,
            input_tokens=200,
            output_tokens=50,
        )
        _request(
            session,
            request_id="req-3",
            run_id="run-2",
            operation="generate",
            provider="ollama",
            model="qwen3.5:9b",
            started_at="2026-01-15T16:00:01+00:00",
            input_tokens=200,
            output_tokens=50,
        )
        _run(
            session,
            run_id="run-3",
            provider="deepseek",
            model="deepseek-flash",
            started_at="2026-01-16T03:30:00+00:00",
            duration_ms=90000,
            status="timeout",
        )
        _request(
            session,
            request_id="req-4",
            run_id="run-3",
            operation="generate",
            provider="deepseek",
            model="deepseek-flash",
            started_at="2026-01-16T03:30:01+00:00",
            status="timeout",
            usage_source="unavailable",
            cost_status="unknown",
        )
        _run(
            session,
            run_id="run-4",
            provider="deepseek",
            model="deepseek-flash",
            started_at="2026-01-16T15:00:00+00:00",
            duration_ms=2000,
            attempt_no=2,
            retry_of="run-1",
            input_tokens=150,
            output_tokens=30,
            cost_status="calculated",
            cost_usd=Decimal("0.002"),
        )
        _request(
            session,
            request_id="req-5",
            run_id="run-4",
            operation="generate",
            provider="deepseek",
            model="deepseek-flash",
            started_at="2026-01-16T15:00:01+00:00",
            input_tokens=150,
            output_tokens=30,
            cost_status="calculated",
            cost_usd=Decimal("0.002"),
        )
        _run(
            session,
            run_id="run-5",
            provider="ollama",
            model="qwen3.5:9b",
            started_at="2026-01-14T15:00:00+00:00",
            duration_ms=1200,
            input_tokens=10,
            output_tokens=2,
        )
        session.add(
            ProviderBudgetLedger(
                run_id="run-1",
                attempt_no=1,
                provider="deepseek",
                model="deepseek-flash",
                state="reserved",
                reserved_usd=Decimal("0.5"),
            )
        )
        session.add(
            ProviderBudgetLedger(
                run_id="run-3",
                attempt_no=1,
                provider="deepseek",
                model="deepseek-flash",
                state="reconciled",
                reserved_usd=Decimal("0.3"),
                settled_usd=Decimal("0.3"),
            )
        )
        session.commit()


def _view(factory, **kwargs):
    with factory() as session:
        return build_usage_view(session, UsageFilters(**kwargs), now=None)


def test_cards_medians_and_coverage(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    _seed(factory)

    view = _view(factory, from_date=date(2026, 1, 1), to_date=date(2026, 1, 31))

    cards = view["cards"]
    assert cards["queries"] == 5
    assert cards["external_requests"] == 4
    assert cards["local_calls"] == 1
    assert cards["input_tokens"] == 460
    assert cards["output_tokens"] == 102
    assert cards["cost_calculated_usd"] == Decimal("0.003")
    assert cards["median_turn_latency_ms"] == 2000
    assert cards["coverage"]["observed"] == 4
    assert cards["coverage"]["unavailable"] == 1
    assert cards["coverage"]["historical_runs"] == 1
    assert cards["pending_reservations_usd"] == Decimal("0.5")
    assert cards["uncertain_committed_usd"] == Decimal("0.3")


def test_date_limits_use_bogota_days(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    _seed(factory)

    view = _view(factory, from_date=date(2026, 1, 15), to_date=date(2026, 1, 15))

    assert view["cards"]["queries"] == 3
    assert view["period"]["from_local"] == "2026-01-15"
    assert view["period"]["to_local"] == "2026-01-15"
    assert view["cards"]["external_requests"] == 3


def test_operation_filter_restricts_runs_without_fabricating(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    _seed(factory)

    view = _view(
        factory,
        from_date=date(2026, 1, 1),
        to_date=date(2026, 1, 31),
        operation="decide",
    )

    assert view["cards"]["queries"] == 1
    assert view["cards"]["external_requests"] == 1
    assert view["cards"]["coverage"]["historical_runs"] == 0


def test_provider_table_and_retries(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    _seed(factory)

    view = _view(
        factory,
        from_date=date(2026, 1, 1),
        to_date=date(2026, 1, 31),
        provider="deepseek",
    )

    assert view["cards"]["queries"] == 3
    (row,) = view["providers"]
    assert row["provider"] == "deepseek"
    assert row["queries"] == 3
    assert row["model_calls"] == 4
    assert row["external_requests"] == 4
    assert row["successes"] == 2
    assert row["errors"] == 1
    assert row["retries"] == 1
    assert row["cost_usd"] == Decimal("0.003")
    assert row["avg_cost_per_query_usd"] == Decimal("0.001")
    assert row["coverage"]["historical_runs"] == 0


def test_invalid_range_is_rejected(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    with factory() as session:
        try:
            build_usage_view(
                session,
                UsageFilters(from_date=date(2026, 2, 2), to_date=date(2026, 1, 1)),
            )
        except UsageFilterError as exc:
            assert "fecha" in str(exc).lower()
        else:  # pragma: no cover - el contrato exige el error
            raise AssertionError("Se esperaba UsageFilterError")


def _evaluation(session) -> None:
    session.add(
        AiEvaluation(
            id="eval-1",
            import_key="005:abc",
            name="Evaluación 005",
            version="005-evaluation-v1",
            frozen_at="2026-11-23",
            dataset_sha256="a" * 64,
            source="report_import",
            detail_level="aggregate",
            provenance_json="{}",
            imported_at="2026-11-23T00:00:00+00:00",
        )
    )
    results = [
        ("ollama", "S01", "approved", 1000, "0.001", True),
        ("deepseek", "S01", "approved", 900, "0.002", True),
        ("anthropic", "S01", "failed", 800, "0.003", True),
        ("ollama", "S02", "failed", 1200, "0.001", None),
        ("deepseek", "S02", "approved", 700, "0.002", True),
        ("anthropic", "S02", "approved", 600, "0.003", True),
        ("ollama", "S08", "approved", 500, "0.001", True),
        ("deepseek", "S08", "blocked", 100, "0.000", None),
        ("anthropic", "S08", "blocked", 100, "0.000", None),
    ]
    for index, (provider, scenario, result, duration, cost, findings) in enumerate(results):
        session.add(
            AiEvaluationResult(
                id=f"res-{index}",
                evaluation_id="eval-1",
                provider=provider,
                model={"ollama": "qwen3.5:9b"}.get(provider, f"{provider}-model"),
                scenario=scenario,
                executed=result != "blocked",
                result=result,
                duration_ms=duration,
                input_tokens=10,
                output_tokens=2,
                usage_source="observed",
                cost_usd=Decimal(cost),
                cost_status="calculated",
                tariff_version="2026-11-22",
                citations_emitted=2,
                citations_valid=2,
                citations_resolvable=2,
                findings_match=findings,
                abstention_ok=None,
                quality_score=Decimal("1.00"),
                quality_method="AI-assisted heuristic; not independent human review",
                manual_review="none",
                detail_level="aggregate",
            )
        )
    session.commit()


def test_comparison_uses_common_scenarios_and_marks_blocked(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    with factory() as session:
        _evaluation(session)
        view = build_comparison_view(session, evaluation_id="eval-1")

    assert view["evaluation"]["id"] == "eval-1"
    assert {item["provider"] for item in view["providers"]} == {
        "ollama",
        "deepseek",
        "anthropic",
    }
    assert view["common_scenarios"] == ["S01", "S02", "S08"]
    assert view["common_executed"] == ["S01", "S02"]
    deepseek = next(item for item in view["providers"] if item["provider"] == "deepseek")
    assert deepseek["executed"] == 2
    assert deepseek["successes"] == 2
    assert deepseek["blocked"] == 1
    assert deepseek["citation_validity"] == 1.0
    assert deepseek["requests_label"] == "Histórico agregado"
