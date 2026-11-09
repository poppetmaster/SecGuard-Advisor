"""Integración: aislamiento de hallazgos entre casos y caso vacío."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import select
from tests.fixtures.conversation import build_env
from tests.fixtures.fakes import FakeEmbedder, FakeTokenCounter, ScriptedGenerator
from tests.fixtures.findings import seed_empty_case, seed_findings

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.conversation.llm import AnswerPayload, ToolDecision
from secguard_advisor.conversation.turn import execute_turn, start_question_turn
from secguard_advisor.db.models import RunToolCall

pytestmark = pytest.mark.integration


def _use(arguments: dict) -> ToolDecision:
    return ToolDecision(use_findings=True, arguments=arguments)


def _no_tool() -> ToolDecision:
    return ToolDecision(use_findings=False, arguments={})


def _ask(env, generator, case_id: str):
    context = start_question_turn(
        env.factory,
        env.settings,
        scope=CaseScope(case_id=case_id),
        question="¿Cuántos hallazgos hay en el activo indicado?",
        generator=generator,
        embedder=FakeEmbedder(),
        index=env.index,
        token_counter=FakeTokenCounter(),
    )
    return context, execute_turn(context)


def _summary(env, run_id: str) -> dict:
    with env.factory() as session:
        call = session.scalar(select(RunToolCall).where(RunToolCall.run_id == run_id))
        assert call is not None
        return json.loads(call.result_summary_json)


def test_two_cases_do_not_share_findings(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    seed_findings(
        env.factory,
        case_id=env.case_id,
        findings=[("activo-alfa", "High", "700001", []), ("activo-alfa", "High", "700002", [])],
    )
    with env.factory() as session:
        from tests.fixtures.corpus import create_case

        case_b = create_case(session, "Caso B")
        session.commit()
    seed_findings(
        env.factory,
        case_id=case_b,
        findings=[("activo-beta", "Critical", "700003", [])],
    )

    context_a, result_a = _ask(
        env,
        ScriptedGenerator(
            payloads=[AnswerPayload(answer="Ninguno.")],
            decisions=[_use({"asset": "activo-beta"}), _no_tool()],
        ),
        env.case_id,
    )
    context_b, result_b = _ask(
        env,
        ScriptedGenerator(
            payloads=[AnswerPayload(answer="Uno.")],
            decisions=[_use({}), _no_tool()],
        ),
        case_b,
    )

    assert result_a.outcome == "answered"
    assert _summary(env, context_a.run_id)["total"] == 0
    assert result_b.outcome == "answered"
    summary_b = _summary(env, context_b.run_id)
    assert summary_b["total"] == 1
    assert summary_b["groups"] == [{"key": "Critical", "count": 1}]


def test_case_without_findings_returns_zero(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    empty_id = seed_empty_case(env.factory)
    generator = ScriptedGenerator(
        payloads=[AnswerPayload(answer="No hay hallazgos registrados.")],
        decisions=[_use({}), _no_tool()],
    )

    context, result = _ask(env, generator, empty_id)

    assert result.outcome == "answered"
    summary = _summary(env, context.run_id)
    assert summary["total"] == 0
    assert summary["groups"] == []
    assert summary["dataset"]["name"] is None
    assert summary["dataset"]["is_synthetic"] is True
    assert "No hay hallazgos registrados" not in json.dumps(summary)
