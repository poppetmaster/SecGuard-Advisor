"""Pruebas de consulta importada desde la conversación y presupuesto."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from tests.fixtures.conversation import build_env
from tests.fixtures.fakes import FakeEmbedder, FakeTokenCounter, ScriptedGenerator

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.conversation.budget import plan_prompt
from secguard_advisor.conversation.llm import AnswerPayload, ToolDecision
from secguard_advisor.conversation.prompts import DECISION_SYSTEM_PROMPT
from secguard_advisor.conversation.turn import execute_turn, start_question_turn
from secguard_advisor.db.models import RunToolCall
from secguard_advisor.vulnerabilities.service import QualysImportService

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


def _use(arguments: dict) -> ToolDecision:
    return ToolDecision(use_findings=True, arguments=arguments)


def _no_tool() -> ToolDecision:
    return ToolDecision(use_findings=False, arguments={})


def test_imported_tool_result_is_in_prompt_and_summary(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    service = QualysImportService(
        env.factory,
        Settings(_env_file=None, storage_dir=tmp_path / "imports"),
    )
    staged = service.stage_import(
        env.case_id,
        "valid.csv",
        (FIXTURES / "qualys_synthetic_valid.csv").read_bytes(),
    )
    service.confirm_import(env.case_id, staged.import_record.id)

    generator = ScriptedGenerator(
        payloads=[AnswerPayload(answer="Hay 3 registros pendientes en la instantánea.", claims=[])],
        decisions=[_use({"origin": "imported", "detail": True, "limit": 2}), _no_tool()],
    )
    context = start_question_turn(
        env.factory,
        env.settings,
        scope=CaseScope(case_id=env.case_id),
        question="¿Cuántos registros importados hay?",
        generator=generator,
        embedder=FakeEmbedder(),
        index=env.index,
        token_counter=FakeTokenCounter(),
    )
    result = execute_turn(context)

    assert result.outcome == "answered"
    prompt = generator.prompts[0]
    assert '"origin": "imported"' in prompt
    assert '"snapshot"' in prompt
    assert '"total": 3' in prompt
    assert env.case_id not in prompt
    assert "Results" not in prompt

    with env.factory() as session:
        call = session.scalar(select(RunToolCall).where(RunToolCall.run_id == context.run_id))
        summary = json.loads(call.result_summary_json)
        assert summary["total"] == 3
        assert summary["snapshot"]["sequence"] == 1
        assert summary["status_group"] == "pending_known"
        assert summary["items_count"] == 2
        assert summary["truncated"] is True
        assert "items" not in summary
        assert "dataset" not in summary


def test_imported_tool_definition_and_budget() -> None:
    assert "origin" in DECISION_SYSTEM_PROMPT
    assert "snapshot_id" in DECISION_SYSTEM_PROMPT
    assert "imported" in DECISION_SYSTEM_PROMPT

    tool_result = {
        "tool": "findings_query",
        "status": "ok",
        "arguments": {"origin": "imported", "detail": True},
        "result": {
            "origin": "imported",
            "snapshot": {"id": "a" * 32, "sequence": 1},
            "status_group": "pending_known",
            "total": 3,
            "groups": [{"key": "4", "count": 2, "label": "Alta"}],
            "priority_counts": {"both_positive": 1},
            "truncated": False,
        },
    }
    plan = plan_prompt(
        question="¿Cuántos registros importados hay?",
        hits=(),
        history=(),
        settings=Settings(_env_file=None),
        counter=FakeTokenCounter(),
        tool_results=(tool_result,),
    )
    assert "snapshot" in plan.user
    assert "Results" not in plan.user
    assert plan.admitted_tokens <= plan.prompt_limit
