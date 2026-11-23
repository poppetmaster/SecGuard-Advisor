"""report-synthesis-v1 validation and factual fallback."""

from typing import ClassVar

from secguard_advisor.db.models import Case, QualysImport
from secguard_advisor.reports.dataset import build_dataset
from secguard_advisor.reports.synthesis import (
    ReportSynthesisPayload,
    SynthesisLine,
    SynthesisSummary,
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

    def __init__(self, payload):
        self.payload = payload

    def generate_structured(self, **_kwargs):
        return self.payload


def _payload(text: str = "Resumen sin cifras libres.", recommendation: str = "Revisar los focos."):
    return ReportSynthesisPayload(
        summary=SynthesisSummary(text=text, claim_refs=["cards.pending.value"]),
        focus=[
            SynthesisLine(
                text="Hay registros pendientes que requieren revisión.",
                basis="csv_fact",
                claim_refs=["cards.pending.value"],
            )
        ],
        recommendations=[
            SynthesisLine(
                text=recommendation, basis="agent_proposal", caveat="Propuesta del agente."
            )
        ],
        limitations=["Limitación de prueba."],
    )


def _dataset(report_context):
    with report_context.session_factory() as session:
        case = session.get(Case, report_context.case_id)
        snapshot = session.get(QualysImport, report_context.snapshot_id)
        return build_dataset(session, case=case, snapshot=snapshot)[0]


def test_valid_synthesis_completes(report_context) -> None:
    dataset = _dataset(report_context)
    with report_context.session_factory() as session:
        result = synthesize_report(
            session,
            report_context.settings,
            case_id=report_context.case_id,
            dataset=dataset,
            enabled=True,
            generator=FakeGenerator(_payload()),
        )
        session.commit()
    assert result.status == "completed"
    assert result.run_id
    assert result.payload["recommendations"][0]["basis"] == "agent_proposal"


def test_free_number_falls_back_to_factual(report_context) -> None:
    dataset = _dataset(report_context)
    with report_context.session_factory() as session:
        result = synthesize_report(
            session,
            report_context.settings,
            case_id=report_context.case_id,
            dataset=dataset,
            enabled=True,
            generator=FakeGenerator(_payload(text="Hay 3 registros pendientes.")),
        )
        session.commit()
    assert result.status == "failed"
    assert "Sin síntesis de IA" in result.payload["limitations"][-1]


def test_documentary_is_presented_as_proposal(report_context) -> None:
    dataset = _dataset(report_context)
    payload = _payload()
    payload.recommendations[0] = SynthesisLine(
        text="Revisar la referencia.",
        basis="documentary",
        evidence_refs=["chunk:demo"],
    )
    with report_context.session_factory() as session:
        result = synthesize_report(
            session,
            report_context.settings,
            case_id=report_context.case_id,
            dataset=dataset,
            enabled=True,
            generator=FakeGenerator(payload),
        )
        session.commit()
    assert result.status == "completed"
    assert result.payload["recommendations"][0]["basis"] == "agent_proposal"
    assert "respaldo semántico no verificado" in result.payload["recommendations"][0]["caveat"]


def test_disabled_synthesis_is_factual(report_context) -> None:
    dataset = _dataset(report_context)
    with report_context.session_factory() as session:
        result = synthesize_report(
            session,
            report_context.settings,
            case_id=report_context.case_id,
            dataset=dataset,
            enabled=False,
        )
        session.commit()
    assert result.status == "not_requested"
    assert "Sin síntesis de IA" in result.payload["limitations"][-1]
