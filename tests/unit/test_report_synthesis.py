"""Report synthesis gates, validation and factual fallback."""

from __future__ import annotations

from decimal import Decimal
from typing import ClassVar

import pytest
from pydantic import SecretStr
from sqlalchemy import select
from tests.fixtures.report_fixtures import add_evidence_chunk

from secguard_advisor.cases.external import authorize_case
from secguard_advisor.config import Settings
from secguard_advisor.conversation.providers.registry import ProviderRegistry
from secguard_advisor.db.models import (
    AiRequest,
    Case,
    ProviderBudgetLedger,
    ProviderUsage,
    QualysImport,
)
from secguard_advisor.reports.dataset import build_dataset
from secguard_advisor.reports.synthesis import (
    ReportSynthesisPayload,
    SynthesisLine,
    SynthesisSummary,
    factual_payload,
    synthesize_report,
)


class FakeGenerator:
    provider = "ollama"
    model = "fake-report"
    identity = None
    last_usage: ClassVar[dict] = {
        "input_tokens": 10,
        "output_tokens": 20,
        "cached_tokens": 0,
        "cache_write_tokens": 0,
        "source": "observed",
        "duration_ms": 5,
    }

    def __init__(self, payload, *, calls: list[str] | None = None):
        self.payload = payload
        self.calls = calls if calls is not None else []

    def generate_structured(self, **_kwargs):
        self.calls.append("call")
        return self.payload

    def close(self):
        return None


class FixedCounter:
    def count(self, _system: str, _user: str) -> int:
        return 100

    def describe(self) -> dict:
        return {"method": "fixed"}


class HugeCounter(FixedCounter):
    def count(self, _system: str, _user: str) -> int:
        return 10**9


def _payload(
    *,
    summary_text: str = "",
    summary_refs: list[str] | None = None,
    recommendation_text: str = "Revisar los focos identificados.",
) -> ReportSynthesisPayload:
    return ReportSynthesisPayload(
        summary=SynthesisSummary(text=summary_text, claim_refs=summary_refs or []),
        focus=[],
        recommendations=[
            SynthesisLine(
                text=recommendation_text,
                basis="agent_proposal",
                caveat="Propuesta del agente.",
            )
        ],
        limitations=[],
    )


def _dataset(report_context):
    with report_context.session_factory() as session:
        case = session.get(Case, report_context.case_id)
        snapshot = session.get(QualysImport, report_context.snapshot_id)
        return build_dataset(session, case=case, snapshot=snapshot)[0]


def _external_settings(settings: Settings, *, budget: str = "1") -> Settings:
    return settings.model_copy(
        update={
            "generation_provider": "deepseek",
            "generation_model": "deepseek-flash",
            "deepseek_api_key": SecretStr("test-key"),
            "external_budget_usd": Decimal(budget),
            "external_run_budget_usd": Decimal(budget),
            "external_tariff_version": "2026-11-22",
        }
    )


def _authorize(factory, case_id: str, scope: str = "fictional_case") -> None:
    with factory() as session:
        authorize_case(
            session,
            case_id=case_id,
            scope=scope,
            authorized_by="Prueba",
        )
        session.commit()


def _make_synthetic_public(report_context) -> None:
    with report_context.session_factory() as session:
        snapshot = session.get(QualysImport, report_context.snapshot_id)
        snapshot.provenance = "synthetic_public"
        session.commit()


def test_valid_synthesis_completes(report_context) -> None:
    dataset = _dataset(report_context)
    factory = report_context.session_factory
    result = synthesize_report(
        factory,
        report_context.settings,
        case_id=report_context.case_id,
        dataset=dataset,
        enabled=True,
        generator=FakeGenerator(_payload()),
    )
    assert result.status == "completed"
    assert result.run_id
    assert result.payload["recommendations"][0]["basis"] == "agent_proposal"
    assert result.payload["summary"]["text"]
    with factory() as session:
        assert session.scalar(select(AiRequest)) is not None
        assert session.scalar(select(ProviderUsage)) is not None


def test_free_number_falls_back_to_factual(report_context) -> None:
    dataset = _dataset(report_context)
    result = synthesize_report(
        report_context.session_factory,
        report_context.settings,
        case_id=report_context.case_id,
        dataset=dataset,
        enabled=True,
        generator=FakeGenerator(_payload(recommendation_text="Hay 3 registros pendientes.")),
    )
    assert result.status == "failed"
    assert "Sin síntesis de IA" in result.payload["limitations"][-1]


def test_contradictory_summary_is_rejected(report_context) -> None:
    dataset = _dataset(report_context)
    assert dataset["cards"]["critical_pending"]["value"] == 2
    result = synthesize_report(
        report_context.session_factory,
        report_context.settings,
        case_id=report_context.case_id,
        dataset=dataset,
        enabled=True,
        generator=FakeGenerator(
            _payload(
                summary_text="Sin vulnerabilidades críticas pendientes",
                summary_refs=["cards.critical_pending.value"],
            )
        ),
    )
    assert result.status == "failed"
    assert result.error_code == "synthesis_invalid"
    assert result.payload["recommendations"] == []


@pytest.mark.parametrize(
    "limitation",
    ["La IP 10.0.0.1 está expuesta.", "Hay 3 vulnerabilidades críticas."],
)
def test_invalid_limitations_are_rejected(report_context, limitation: str) -> None:
    dataset = _dataset(report_context)
    payload = _payload()
    payload.limitations = [limitation]
    result = synthesize_report(
        report_context.session_factory,
        report_context.settings,
        case_id=report_context.case_id,
        dataset=dataset,
        enabled=True,
        generator=FakeGenerator(payload),
    )
    assert result.status == "failed"
    assert result.error_code == "synthesis_invalid"


def test_invented_citation_is_rejected(report_context) -> None:
    dataset = _dataset(report_context)
    payload = _payload()
    payload.recommendations[0] = SynthesisLine(
        text="Revisar la referencia.",
        basis="documentary",
        evidence_refs=["chunk:inexistente"],
    )
    result = synthesize_report(
        report_context.session_factory,
        report_context.settings,
        case_id=report_context.case_id,
        dataset=dataset,
        enabled=True,
        generator=FakeGenerator(payload),
    )
    assert result.status == "failed"
    assert result.error_code == "synthesis_invalid"


def test_valid_citation_is_kept_as_proposal(report_context) -> None:
    chunk_id = add_evidence_chunk(report_context.session_factory, report_context.case_id)
    dataset = _dataset(report_context)
    payload = _payload()
    payload.recommendations[0] = SynthesisLine(
        text="Revisar la evidencia documental.",
        basis="documentary",
        evidence_refs=[f"chunk:{chunk_id}"],
    )
    result = synthesize_report(
        report_context.session_factory,
        report_context.settings,
        case_id=report_context.case_id,
        dataset=dataset,
        enabled=True,
        generator=FakeGenerator(payload),
    )
    assert result.status == "completed"
    assert result.payload["recommendations"][0]["basis"] == "agent_proposal"
    assert "respaldo semántico no verificado" in result.payload["recommendations"][0]["caveat"]


def test_disabled_synthesis_is_factual(report_context) -> None:
    dataset = _dataset(report_context)
    result = synthesize_report(
        report_context.session_factory,
        report_context.settings,
        case_id=report_context.case_id,
        dataset=dataset,
        enabled=False,
    )
    assert result.status == "not_requested"
    assert "Sin síntesis de IA" in result.payload["limitations"][-1]


def test_private_qualys_is_blocked_for_external_provider(report_context) -> None:
    dataset = _dataset(report_context)
    _authorize(report_context.session_factory, report_context.case_id, "fictional_case")
    calls: list[str] = []
    result = synthesize_report(
        report_context.session_factory,
        _external_settings(report_context.settings),
        case_id=report_context.case_id,
        dataset=dataset,
        enabled=True,
        generator=FakeGenerator(_payload(), calls=calls),
    )
    assert result.status == "unavailable"
    assert result.error_code == "external_content_blocked"
    assert calls == []


def test_public_corpus_scope_does_not_cover_qualys(report_context) -> None:
    _make_synthetic_public(report_context)
    dataset = _dataset(report_context)
    _authorize(report_context.session_factory, report_context.case_id, "public_corpus")
    calls: list[str] = []
    result = synthesize_report(
        report_context.session_factory,
        _external_settings(report_context.settings),
        case_id=report_context.case_id,
        dataset=dataset,
        enabled=True,
        generator=FakeGenerator(_payload(), calls=calls),
    )
    assert result.error_code == "external_content_blocked"
    assert calls == []


def test_reservation_and_consumption_are_recorded(report_context) -> None:
    _make_synthetic_public(report_context)
    dataset = _dataset(report_context)
    _authorize(report_context.session_factory, report_context.case_id, "fictional_case")
    result = synthesize_report(
        report_context.session_factory,
        _external_settings(report_context.settings),
        case_id=report_context.case_id,
        dataset=dataset,
        enabled=True,
        generator=FakeGenerator(_payload()),
        counter=FixedCounter(),
    )
    assert result.status == "completed"
    with report_context.session_factory() as session:
        ledger = session.scalar(select(ProviderBudgetLedger))
        request = session.scalar(select(AiRequest))
        usage = session.scalar(select(ProviderUsage))
    assert ledger is not None and ledger.state == "settled"
    assert request is not None and request.input_tokens == 10 and request.output_tokens == 20
    assert request.cost_status == "calculated" and request.cost_usd is not None
    assert usage is not None and usage.tariff_version == "2026-11-22"


def test_exhausted_budget_does_not_call_provider(report_context) -> None:
    _make_synthetic_public(report_context)
    dataset = _dataset(report_context)
    _authorize(report_context.session_factory, report_context.case_id, "fictional_case")
    calls: list[str] = []
    result = synthesize_report(
        report_context.session_factory,
        _external_settings(report_context.settings, budget="0.000001"),
        case_id=report_context.case_id,
        dataset=dataset,
        enabled=True,
        generator=FakeGenerator(_payload(), calls=calls),
        counter=FixedCounter(),
    )
    assert result.status == "failed"
    assert result.error_code in {"budget_exceeded", "tariff_unavailable"}
    assert calls == []


def test_context_excess_does_not_call_provider(report_context) -> None:
    dataset = _dataset(report_context)
    calls: list[str] = []
    result = synthesize_report(
        report_context.session_factory,
        report_context.settings,
        case_id=report_context.case_id,
        dataset=dataset,
        enabled=True,
        generator=FakeGenerator(_payload(), calls=calls),
        counter=HugeCounter(),
    )
    assert result.status == "failed"
    assert result.error_code == "context_budget_exceeded"
    assert calls == []


def test_provider_initialization_failure_is_factual(report_context, monkeypatch) -> None:
    dataset = _dataset(report_context)

    def fail_create(self, **_kwargs):
        raise RuntimeError("initialization failed")

    monkeypatch.setattr(ProviderRegistry, "create", fail_create)
    result = synthesize_report(
        report_context.session_factory,
        report_context.settings,
        case_id=report_context.case_id,
        dataset=dataset,
        enabled=True,
        counter=FixedCounter(),
    )
    assert result.status == "failed"
    assert result.error_code == "synthesis_error"
    assert result.payload["recommendations"] == []


def test_factual_payload_has_no_recommendations(report_context) -> None:
    dataset = _dataset(report_context)
    payload = factual_payload(dataset, "motivo")
    assert payload["recommendations"] == []
    assert payload["summary"]["text"]
    assert payload["limitations"]
