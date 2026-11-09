"""Límites del turno: pasos, herramientas, reparación y tiempos."""

from __future__ import annotations

from pathlib import Path

from tests.fixtures.conversation import build_env
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
from secguard_advisor.conversation.nodes import route_after_validate
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
