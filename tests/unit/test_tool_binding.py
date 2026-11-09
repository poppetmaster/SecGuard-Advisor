"""Pruebas de la vinculación de findings_query al grafo."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import select
from tests.fixtures.conversation import build_env
from tests.fixtures.fakes import FakeEmbedder, FakeTokenCounter, ScriptedGenerator
from tests.fixtures.findings import seed_findings

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.conversation.llm import AnswerPayload, ToolDecision
from secguard_advisor.conversation.turn import execute_turn, start_question_turn
from secguard_advisor.db.models import Run, RunToolCall
from secguard_advisor.tools.findings import ToolExecutionError, ToolTimeout

FINDINGS = [
    ("api-gateway", "High", "900001", []),
    ("api-gateway", "High", "900002", []),
    ("portal", "High", "900003", ["CVE-2024-0001"]),
    ("portal", "Low", "900004", []),
]


def _use(arguments: dict) -> ToolDecision:
    return ToolDecision(use_findings=True, arguments=arguments)


def _no_tool() -> ToolDecision:
    return ToolDecision(use_findings=False, arguments={})


def _answer(text: str = "Hay 3 hallazgos de severidad High.") -> AnswerPayload:
    return AnswerPayload(answer=text, claims=[])


def _ask(env, generator, question: str = "¿Cuántos hallazgos High hay?"):
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


@pytest.fixture
def env(tmp_path: Path):
    environment = build_env(tmp_path, with_documents=False, min_score=-1.0)
    seed_findings(environment.factory, findings=FINDINGS, case_id=environment.case_id)
    yield environment


def test_model_requested_tool_is_executed_and_recorded(env) -> None:
    generator = ScriptedGenerator(
        payloads=[_answer()],
        decisions=[_use({"severity": "High", "group_by": "asset"}), _no_tool()],
    )

    context, result = _ask(env, generator)

    assert result.outcome == "answered"
    assert generator.decision_calls == 2
    assert generator.prompts[0].count("Resultados de herramientas") == 1
    assert '"total": 3' in generator.prompts[0]
    assert env.case_id not in generator.prompts[0]
    with env.factory() as session:
        run = session.get(Run, context.run_id)
        assert run.tool_calls_count == 1
        call = session.scalar(select(RunToolCall).where(RunToolCall.run_id == run.id))
        assert call is not None
        assert call.origin == "model_requested"
        assert call.status == "ok"
        assert json.loads(call.arguments_json) == {
            "severity": "High",
            "group_by": "asset",
        }
        summary = json.loads(call.result_summary_json)
        assert summary["total"] == 3
        assert "items" not in summary
        assert summary["dataset"]["is_synthetic"] is True


def test_no_request_does_not_execute_tools(env) -> None:
    generator = ScriptedGenerator(payloads=[_answer("No necesito la herramienta.")])

    context, result = _ask(env, generator)

    assert result.outcome == "insufficient_evidence"
    assert generator.decision_calls == 1
    with env.factory() as session:
        run = session.get(Run, context.run_id)
        assert run.tool_calls_count == 0
        assert session.scalar(select(RunToolCall).where(RunToolCall.run_id == run.id)) is None


def test_invalid_arguments_are_returned_for_correction(env) -> None:
    generator = ScriptedGenerator(
        payloads=[_answer()],
        decisions=[_use({"severity": "Baja"}), _use({"severity": "High"})],
    )

    context, result = _ask(env, generator)

    assert result.outcome == "answered"
    assert generator.decision_calls == 2
    assert "invalid_severity" in generator.decision_prompts[1]
    assert '"total": 3' in generator.prompts[0]
    with env.factory() as session:
        calls = list(
            session.scalars(
                select(RunToolCall)
                .where(RunToolCall.run_id == context.run_id)
                .order_by(RunToolCall.seq)
            )
        )
        assert [(call.status, call.error_code) for call in calls] == [
            ("invalid_arguments", "invalid_severity"),
            ("ok", None),
        ]


def test_case_id_in_arguments_is_rejected(env) -> None:
    generator = ScriptedGenerator(
        payloads=[_answer("No pude consultar.")],
        decisions=[_use({"case_id": "a" * 32}), _no_tool()],
    )

    context, result = _ask(env, generator)

    assert generator.decision_calls == 2
    assert "invalid_arguments" in generator.decision_prompts[1]
    with env.factory() as session:
        call = session.scalar(select(RunToolCall).where(RunToolCall.run_id == context.run_id))
        assert call.status == "invalid_arguments"
        assert call.error_code == "invalid_arguments"
    assert result.outcome == "insufficient_evidence"


def test_tool_call_limit_is_enforced(env) -> None:
    generator = ScriptedGenerator(
        payloads=[_answer("Hay 3 High y 1 Low.")],
        decisions=[
            _use({"severity": "High"}),
            _use({"severity": "Low"}),
            _use({"severity": "Info"}),
        ],
    )

    context, _result = _ask(env, generator)

    assert generator.decision_calls == 2
    with env.factory() as session:
        calls = list(
            session.scalars(select(RunToolCall).where(RunToolCall.run_id == context.run_id))
        )
        assert len(calls) == 2
        run = session.get(Run, context.run_id)
        assert run.tool_calls_count == 2


def test_database_failure_closes_the_turn_as_failed(env, monkeypatch) -> None:
    def broken(self, arguments):
        raise ToolExecutionError("sin base")

    monkeypatch.setattr("secguard_advisor.tools.findings.FindingsQuery.execute", broken)
    generator = ScriptedGenerator(payloads=[_answer()], decisions=[_use({"severity": "High"})])

    _context, result = _ask(env, generator)

    assert result.status == "failed"
    assert result.error_code == "tool_failed"
    assert result.http_status == 500


def test_tool_timeout_closes_the_turn_as_timeout(env, monkeypatch) -> None:
    def slow(self, arguments):
        raise ToolTimeout("lento")

    monkeypatch.setattr("secguard_advisor.tools.findings.FindingsQuery.execute", slow)
    generator = ScriptedGenerator(payloads=[_answer()], decisions=[_use({"severity": "High"})])

    _context, result = _ask(env, generator)

    assert result.status == "timeout"
    assert result.error_code == "tool_timeout"
    assert result.http_status == 504


def test_detail_summary_keeps_counts_without_rows(env) -> None:
    generator = ScriptedGenerator(
        payloads=[_answer("Hay 4 hallazgos.")],
        decisions=[_use({"detail": True, "limit": 2}), _no_tool()],
    )

    context, _result = _ask(env, generator)

    with env.factory() as session:
        call = session.scalar(select(RunToolCall).where(RunToolCall.run_id == context.run_id))
        summary = json.loads(call.result_summary_json)
        assert summary["total"] == 4
        assert summary["items_count"] == 2
        assert summary["truncated"] is True
        assert "items" not in summary
    assert '"cves"' in generator.prompts[0]
