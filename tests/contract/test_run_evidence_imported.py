"""Evidencia histórica de una consulta importada frente al detalle actual."""

from __future__ import annotations

from pathlib import Path

from tests.fixtures.conversation import build_env
from tests.fixtures.fakes import FakeEmbedder, FakeTokenCounter, ScriptedGenerator

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.conversation.llm import AnswerPayload, ToolDecision
from secguard_advisor.conversation.turn import execute_turn, start_question_turn
from secguard_advisor.evidence.runs import serialize_tool_calls
from secguard_advisor.vulnerabilities.service import QualysImportService

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


def _import(env, filename: str) -> str:
    service = QualysImportService(env.factory, env.settings)
    staged = service.stage_import(
        env.case_id,
        filename,
        (FIXTURES / filename).read_bytes(),
    )
    service.confirm_import(env.case_id, staged.import_record.id)
    return staged.import_record.id


def test_historical_detail_uses_persisted_snapshot_not_latest(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    _import(env, "qualys_synthetic_valid.csv")
    second_id = _import(env, "qualys_synthetic_mixed.csv")

    generator = ScriptedGenerator(
        payloads=[
            AnswerPayload(
                answer="La instantánea tiene 2 registros pendientes conocidos.", claims=[]
            )
        ],
        decisions=[
            ToolDecision(
                use_findings=True,
                arguments={"origin": "imported", "detail": True, "limit": 10},
            ),
            ToolDecision(use_findings=False, arguments={}),
        ],
    )
    context = start_question_turn(
        env.factory,
        env.settings,
        scope=CaseScope(case_id=env.case_id),
        question="¿Cuántos registros pendientes hay en la instantánea?",
        generator=generator,
        embedder=FakeEmbedder(),
        index=env.index,
        token_counter=FakeTokenCounter(),
    )
    result = execute_turn(context)
    assert result.outcome == "answered"

    # Una instantánea nueva no debe cambiar el detalle de la ejecución anterior.
    _import(env, "qualys_synthetic_second.csv")

    with env.factory() as session:
        calls = serialize_tool_calls(
            session,
            context.run_id,
            factory=env.factory,
            scope=CaseScope(case_id=env.case_id),
        )
    assert len(calls) == 1
    call = calls[0]
    assert call["status"] == "ok"
    assert call["arguments"].get("snapshot_id") is None
    assert call["summary"]["snapshot"]["id"] == second_id
    assert call["summary"]["snapshot"]["sequence"] == 2
    assert call["detail_source"] == "current_query"
    assert call["detail_snapshot"]["id"] == second_id
    assert call["detail_snapshot"]["sequence"] == 2
    assert {item["title"] for item in call["detail_items"]} == {
        "Synthetic expl only",
        "Synthetic mal only",
    }
    assert call["summary"]["total"] == 2
    assert len(call["detail_items"]) == 2
