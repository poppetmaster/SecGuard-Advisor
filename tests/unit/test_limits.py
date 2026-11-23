"""Límites del turno: pasos, herramientas, reparación y tiempos."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from tests.fixtures.conversation import CASE_TEXT, build_env
from tests.fixtures.fakes import FakeEmbedder, FakeTokenCounter

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.conversation.llm import (
    AnswerPayload,
    Claim,
    ModelTimeout,
    RunTimeout,
    StepLimit,
    ToolDecision,
)
from secguard_advisor.conversation.nodes import (
    _format_tool_result_answer,
    _model_timeout,
    persist,
    route_after_validate,
)
from secguard_advisor.conversation.persistence import CitationDraft
from secguard_advisor.conversation.turn import execute_turn, start_question_turn


class RecordingGenerator:
    """Generador que registra los tiempos recibidos y puede fallar."""

    model = "fake-generator"
    digest = "digest-fake"

    def __init__(self, *, decisions=(), payloads=(), error=None) -> None:
        self.decisions = list(decisions)
        self.payloads = list(payloads)
        self.error = error
        self.decision_timeouts: list[float | None] = []
        self.generate_timeouts: list[float | None] = []

    def decide(self, *, system: str, user: str, timeout_seconds=None):
        self.decision_timeouts.append(timeout_seconds)
        if self.error is not None:
            raise self.error
        if self.decisions:
            return self.decisions.pop(0)
        return ToolDecision(use_findings=False, arguments={})

    def generate(self, *, system: str, user: str, timeout_seconds=None):
        self.generate_timeouts.append(timeout_seconds)
        if self.error is not None:
            raise self.error
        if self.payloads:
            return self.payloads.pop(0)
        return AnswerPayload(answer="respuesta", claims=[])


def _settings() -> dict:
    return {
        "run_timeout_seconds": 120.0,
        "llm_timeout_seconds": 90.0,
        "max_graph_steps": 8,
        "max_tool_calls": 2,
    }


def _ask_with_context(env, generator, question: str = "¿Cuántos hallazgos High hay?"):
    context = start_question_turn(
        env.factory,
        env.settings,
        scope=CaseScope(case_id=env.case_id),
        question=question,
        generator=generator,
        embedder=FakeEmbedder(),
        index=env.index,
        token_counter=FakeTokenCounter(),
    )
    return context, execute_turn(context)


def _ask(env, generator, question: str = "¿Cuántos hallazgos High hay?"):
    _context, result = _ask_with_context(env, generator, question)
    return result


def test_approved_defaults_are_configured() -> None:
    settings = Settings(_env_file=None)
    assert settings.max_graph_steps == 8
    assert settings.max_tool_calls == 2
    assert settings.run_timeout_seconds == 120.0
    assert settings.llm_timeout_seconds == 90.0


def test_decision_and_tool_operations_count_as_steps(tmp_path: Path) -> None:
    env = build_env(
        tmp_path,
        with_documents=False,
        min_score=-1.0,
        settings_overrides={"max_graph_steps": 1},
    )
    generator = RecordingGenerator(
        decisions=[ToolDecision(use_findings=True, arguments={"severity": "High"})]
    )

    result = _ask(env, generator)

    assert result.status == "failed"
    assert result.error_code == "step_limit"
    assert generator.decision_timeouts


def test_agent_generation_also_counts_as_a_step(tmp_path: Path) -> None:
    env = build_env(
        tmp_path,
        with_documents=False,
        min_score=-1.0,
        settings_overrides={"max_graph_steps": 1},
    )
    generator = RecordingGenerator()

    result = _ask(env, generator)

    assert result.status == "failed"
    assert result.error_code == "step_limit"
    assert generator.generate_timeouts == []


def test_turn_deadline_is_checked_before_the_decision(tmp_path: Path) -> None:
    env = build_env(
        tmp_path,
        with_documents=False,
        min_score=-1.0,
        settings_overrides={"run_timeout_seconds": 0.0},
    )
    generator = RecordingGenerator()

    result = _ask(env, generator)

    assert result.status == "timeout"
    assert result.error_code == "run_timeout"
    assert generator.decision_timeouts == []


def test_per_call_timeout_maps_to_model_timeout(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    generator = RecordingGenerator(error=ModelTimeout("90 s"))

    result = _ask(env, generator)

    assert result.status == "timeout"
    assert result.error_code == "model_timeout"


def test_remaining_turn_time_caps_each_model_call(tmp_path: Path) -> None:
    env = build_env(
        tmp_path,
        with_documents=False,
        min_score=-1.0,
        settings_overrides={"run_timeout_seconds": 10.0, "llm_timeout_seconds": 90.0},
    )
    generator = RecordingGenerator()

    result = _ask(env, generator)

    assert result.status == "succeeded"
    assert generator.decision_timeouts
    assert generator.generate_timeouts
    first = generator.decision_timeouts[0]
    second = generator.decision_timeouts[-1] if len(generator.decision_timeouts) > 1 else first
    assert first is not None and 0 < first <= 10.0
    assert second is not None and second <= first
    assert all(
        timeout is None or timeout <= 10.0
        for timeout in (*generator.decision_timeouts, *generator.generate_timeouts)
    )


def test_step_limit_exception_is_classified() -> None:
    assert issubclass(StepLimit, Exception)


def test_run_timeout_exception_is_classified() -> None:
    assert issubclass(RunTimeout, Exception)


def test_synthesis_question_uses_case_fallback_when_threshold_filters_everything(
    tmp_path: Path,
) -> None:
    env = build_env(tmp_path, min_score=1.1)
    generator = RecordingGenerator(
        payloads=[
            AnswerPayload(
                answer=(
                    "Informe: el cifrado en reposo está documentado. "
                    "Recomendación propuesta: revisar el registro de accesos."
                ),
                claims=[
                    Claim(
                        text="El control aplica cifrado en reposo.",
                        chunk_ids=["S1"],
                        quote=CASE_TEXT,
                    )
                ],
                missing_info=["No hay datos sobre frecuencia de revisión."],
            )
        ]
    )

    result = _ask(
        env,
        generator,
        question="Prepará un informe breve con resumen, evidencias y recomendaciones.",
    )

    assert result.status == "succeeded"
    assert result.outcome == "answered"
    with env.factory() as session:
        from secguard_advisor.db.models import Run

        run = session.scalar(select(Run).where(Run.case_id == env.case_id))
        assert run is not None
    assert generator.generate_timeouts


def test_no_model_call_starts_with_less_than_one_second_left() -> None:
    import time
    from types import SimpleNamespace

    context = SimpleNamespace(
        deps=SimpleNamespace(
            settings=SimpleNamespace(run_timeout_seconds=0.2, provider_timeout_seconds=90.0)
        ),
        started_perf=time.perf_counter(),
    )

    with pytest.raises(RunTimeout):
        _model_timeout(context)


def test_report_answer_includes_recommendations_and_limitations(tmp_path: Path) -> None:
    env = build_env(tmp_path, min_score=-1.0)
    generator = RecordingGenerator(
        payloads=[
            AnswerPayload(
                answer="Resumen documentado del control.",
                claims=[
                    Claim(
                        text="El control aplica cifrado en reposo.",
                        chunk_ids=["S1"],
                        quote=CASE_TEXT,
                    )
                ],
                missing_info=["No hay datos sobre frecuencia de revisión."],
                recommendations=["Revisar el registro de accesos."],
            )
        ]
    )

    result = _ask(env, generator, question="Prepará un informe breve.")

    assert result.outcome == "answered"
    with env.factory() as session:
        from secguard_advisor.db.models import Message

        message = session.scalar(select(Message).where(Message.role == "assistant"))
    assert message is not None
    assert "Recomendaciones propuestas por el agente" in message.content
    assert "1. Revisar el registro de accesos." in message.content
    assert "Limitaciones o información faltante" in message.content


def test_report_without_missing_info_adds_a_standard_limitation(tmp_path: Path) -> None:
    env = build_env(tmp_path, min_score=-1.0)
    generator = RecordingGenerator(
        payloads=[
            AnswerPayload(
                answer="Resumen documentado.",
                claims=[
                    Claim(
                        text="El control aplica cifrado en reposo.",
                        chunk_ids=["S1"],
                        quote=CASE_TEXT,
                    )
                ],
                missing_info=[],
                recommendations=["Revisar el registro de accesos."],
            )
        ]
    )

    _ask(env, generator, question="Prepará un informe breve.")

    with env.factory() as session:
        from secguard_advisor.db.models import Message

        message = session.scalar(select(Message).where(Message.role == "assistant"))
    assert message is not None
    assert "Limitaciones: este informe se basa solo en la evidencia recuperada" in message.content


def test_exclusive_tool_evidence_persists_without_document_citations() -> None:
    payload = AnswerPayload(answer="Hay 3 hallazgos High.", claims=[])
    state = {
        "citations": (),
        "payload": payload,
        "hits": (),
        "tool_results": ({"tool": "findings_query", "status": "ok", "result": {"total": 3}},),
        "repaired": False,
    }

    assert route_after_validate(state) == "persist"


def test_tool_evidence_with_invalid_document_claim_requires_repair() -> None:
    payload = AnswerPayload(
        answer="Hay 3 hallazgos High.",
        claims=[Claim(text="dato", chunk_ids=["S9"], quote="no existe")],
    )
    state = {
        "citations": (),
        "rejected": ("cita rechazada",),
        "payload": payload,
        "hits": (),
        "tool_results": ({"tool": "findings_query", "status": "ok", "result": {"total": 3}},),
        "repaired": False,
    }

    assert route_after_validate(state) == "repair"
    state["repaired"] = True
    assert route_after_validate(state) == "abstain"


def test_persist_does_not_mark_answered_when_a_citation_is_rejected(
    tmp_path: Path,
) -> None:
    env = build_env(tmp_path, min_score=-1.0)
    context = start_question_turn(
        env.factory,
        env.settings,
        scope=CaseScope(case_id=env.case_id),
        question="¿Qué controles aplican?",
        generator=RecordingGenerator(),
        embedder=FakeEmbedder(),
        index=env.index,
        token_counter=FakeTokenCounter(),
    )
    valid = CitationDraft(
        chunk_id=env.case_document.chunk_ids[0],
        document_id=env.case_document.document_id,
        version_id=env.case_document.version_id,
        page=1,
        section=None,
        quote=CASE_TEXT,
        locator="p:1#0",
        check_status="valid",
        check_reason=None,
    )
    rejected = CitationDraft(
        chunk_id="",
        document_id="",
        version_id="",
        page=None,
        section=None,
        quote="cita rechazada",
        locator="",
        check_status="rejected",
        check_reason="quote_not_found",
    )
    state = {
        "payload": AnswerPayload(answer="Respuesta mixta.", claims=[]),
        "citations": (valid,),
        "rejected": (rejected,),
        "hits": (),
        "tool_results": (),
        "steps": (),
        "tool_records": (),
    }

    persist(state, {"configurable": {"runtime": context, "memory": None}})

    with env.factory() as session:
        from secguard_advisor.db.models import Run

        run = session.get(Run, context.run_id)
        assert run is not None
        assert run.outcome == "insufficient_evidence"


def test_tool_fallback_summary_is_deterministic_and_marks_scope() -> None:
    result = {
        "origin": "imported",
        "total": 3,
        "groups": [{"key": "a", "label": "Alta", "count": 2}],
        "snapshot": {"id": "snapshot-1", "sequence": 2},
        "status_group": "pending_known",
    }
    state = {
        "tool_results": (
            {
                "status": "ok",
                "arguments": {"origin": "imported", "severity_level": 4},
                "result": result,
            },
        ),
        "rejected": ("cita rechazada",),
    }

    text = _format_tool_result_answer(state, state["tool_results"][0])

    assert text.startswith("Resultado de herramienta; síntesis del modelo no disponible.")
    assert '"origin": "imported"' in text
    assert "Total: 3." in text
    assert "a (Alta): 2" in text
    assert "secuencia 2" in text
    assert "cita(s) rechazada(s)" in text
    assert "No es una respuesta documental verificada" in text
    assert "case_id" not in text


def test_tool_fallback_handles_zero_result_and_historical_snapshot() -> None:
    state = {
        "tool_results": (
            {
                "status": "ok",
                "arguments": {},
                "result": {
                    "origin": "synthetic",
                    "total": 0,
                    "groups": [],
                    "snapshot": {"id": "old-snapshot", "sequence": 7},
                },
            },
        )
    }

    text = _format_tool_result_answer(state, state["tool_results"][0])

    assert "Total: 0." in text
    assert "Grupos: sin grupos." in text
    assert "secuencia 7" in text


def test_persist_uses_tool_fallback_when_model_has_no_answer(tmp_path: Path) -> None:
    env = build_env(tmp_path, min_score=-1.0)
    context = start_question_turn(
        env.factory,
        env.settings,
        scope=CaseScope(case_id=env.case_id),
        question="¿Cuántos hallazgos High hay por activo?",
        generator=RecordingGenerator(),
        embedder=FakeEmbedder(),
        index=env.index,
        token_counter=FakeTokenCounter(),
    )
    result = {
        "origin": "synthetic",
        "total": 3,
        "groups": [{"key": "api-gateway", "count": 2}],
        "snapshot": {"id": "snap-1", "sequence": 1},
    }
    state = {
        "payload": AnswerPayload(answer="", claims=[]),
        "citations": (),
        "rejected": (),
        "hits": (),
        "tool_results": ({"status": "ok", "arguments": {"origin": "synthetic"}, "result": result},),
        "tool_records": (),
        "steps": (),
    }

    persist(state, {"configurable": {"runtime": context, "memory": None}})

    with env.factory() as session:
        from secguard_advisor.db.models import Message, Run

        run = session.get(Run, context.run_id)
        assert run is not None
        message = session.get(Message, run.answer_message_id)
    assert message is not None
    assert message.content.startswith(
        "Resultado de herramienta; síntesis del modelo no disponible."
    )
    assert "Total: 3." in message.content
    assert run.outcome == "insufficient_evidence"


def test_partial_citation_rejection_repairs_once_then_abstains() -> None:
    payload = AnswerPayload(
        answer="La política exige MFA y el control de acceso está documentado.",
        claims=[
            Claim(text="MFA", chunk_ids=["S1"], quote="texto"),
            Claim(text="control", chunk_ids=["S9"], quote="no existe"),
        ],
    )
    state = {
        "citations": ("cita válida",),
        "rejected": ("cita rechazada",),
        "payload": payload,
        "hits": ("hit",),
        "tool_results": (),
        "repaired": False,
    }

    assert route_after_validate(state) == "repair"
    state["repaired"] = True
    assert route_after_validate(state) == "abstain"


def test_mixed_response_with_valid_citations_and_tool_evidence_persists() -> None:
    payload = AnswerPayload(
        answer="La política exige MFA y hay 3 hallazgos.",
        claims=[Claim(text="MFA", chunk_ids=["S1"], quote="texto")],
    )
    state = {
        "citations": ("cita válida",),
        "rejected": (),
        "payload": payload,
        "hits": ("hit",),
        "tool_results": ({"tool": "findings_query", "status": "ok", "result": {"total": 3}},),
        "repaired": False,
    }

    assert route_after_validate(state) == "persist"


def test_failed_or_empty_tool_does_not_back_a_documentless_answer() -> None:
    payload = AnswerPayload(answer="Hay 3 hallazgos High.", claims=[])
    for tool_result in (
        {"tool": "findings_query", "status": "error"},
        {"tool": "findings_query", "status": "ok", "result": {}},
    ):
        state = {
            "citations": (),
            "rejected": (),
            "payload": payload,
            "hits": (),
            "tool_results": (tool_result,),
            "repaired": False,
        }
        assert route_after_validate(state) == "abstain"


def test_only_one_repair_route_is_available() -> None:
    payload = AnswerPayload(
        answer="afirmación",
        claims=[Claim(text="afirmación", chunk_ids=["S1"], quote="texto")],
    )
    state = {"citations": (), "payload": payload, "hits": ("hit",), "repaired": True}

    assert route_after_validate(state) == "abstain"

    state["repaired"] = False
    assert route_after_validate(state) == "repair"


def test_tool_call_limit_is_recorded_in_the_decision_step(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    generator = RecordingGenerator(
        decisions=[
            ToolDecision(use_findings=True, arguments={"severity": "High"}),
            ToolDecision(use_findings=True, arguments={"severity": "Low"}),
            ToolDecision(use_findings=True, arguments={"severity": "Info"}),
        ],
        payloads=[AnswerPayload(answer="respuesta", claims=[])],
    )

    context, result = _ask_with_context(env, generator)

    assert result.status == "succeeded"
    with env.factory() as session:
        from sqlalchemy import select

        from secguard_advisor.db.models import Run, RunStep

        run = session.get(Run, context.run_id)
        assert run.tool_calls_count == 2
        decide_steps = list(
            session.scalars(
                select(RunStep)
                .where(RunStep.run_id == run.id, RunStep.name == "decide")
                .order_by(RunStep.seq)
            )
        )
        details = [step.detail_json or "" for step in decide_steps]
    assert any("tool_call_limit" in detail for detail in details)
