"""Integración: pregunta respondida solo con findings_query, sin fuentes."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select
from tests.fixtures.conversation import build_env
from tests.fixtures.fakes import FakeEmbedder, FakeTokenCounter, ScriptedGenerator
from tests.fixtures.findings import seed_findings

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.conversation.llm import AnswerPayload, ToolDecision
from secguard_advisor.conversation.turn import execute_turn, start_question_turn
from secguard_advisor.db.models import Finding, MessageCitation, Run, RunToolCall

pytestmark = pytest.mark.integration

FINDINGS = [
    ("api-gateway", "High", "900001", []),
    ("api-gateway", "High", "900002", []),
    ("portal", "High", "900003", []),
    ("portal", "Low", "900004", []),
]


def test_tool_only_question_is_answered_without_documentary_citations(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    seed_findings(env.factory, findings=FINDINGS, case_id=env.case_id)
    generator = ScriptedGenerator(
        payloads=[
            AnswerPayload(
                answer="Hay 3 hallazgos High: 2 en api-gateway y 1 en portal.",
                claims=[],
            )
        ],
        decisions=[
            ToolDecision(
                use_findings=True,
                arguments={"severity": "High", "group_by": "asset"},
            ),
            ToolDecision(use_findings=False, arguments={}),
        ],
    )

    context = start_question_turn(
        env.factory,
        env.settings,
        scope=CaseScope(case_id=env.case_id),
        question="¿Cuántos hallazgos High hay y cómo se agrupan por activo?",
        generator=generator,
        embedder=FakeEmbedder(),
        index=env.index,
        token_counter=FakeTokenCounter(),
    )
    result = execute_turn(context)

    assert result.status == "succeeded"
    assert result.outcome == "answered"
    with env.factory() as session:
        assert session.scalar(select(func.count()).select_from(MessageCitation)) == 0
        run = session.get(Run, context.run_id)
        assert run.tool_calls_count == 1
        call = session.scalar(select(RunToolCall).where(RunToolCall.run_id == run.id))
        assert call.status == "ok"
        expected = session.scalar(
            select(func.count())
            .select_from(Finding)
            .where(Finding.case_id == env.case_id, Finding.severity_label == "High")
        )
        assert expected == 3
    assert '"total": 3' in generator.prompts[0]
    assert "No se recuperaron fuentes documentales" in generator.prompts[0]
