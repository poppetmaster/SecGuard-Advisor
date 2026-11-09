"""La importación Qualys no crea documentos, vectores ni citas documentales."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select
from tests.fixtures.conversation import build_env
from tests.fixtures.fakes import FakeEmbedder, FakeTokenCounter, ScriptedGenerator

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.conversation.llm import AnswerPayload, Claim, ToolDecision
from secguard_advisor.conversation.turn import execute_turn, start_question_turn
from secguard_advisor.db.models import (
    Document,
    DocumentChunk,
    MessageCitation,
    Run,
    RunToolCall,
)
from secguard_advisor.retrieval.collections import case_scope, public_scope
from secguard_advisor.vulnerabilities.service import QualysImportService

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


def _vector_count(index, case_id: str) -> int:
    return index.count(public_scope(), "fake-embedding", 4) + index.count(
        case_scope(case_id), "fake-embedding", 4
    )


def _counts(factory) -> tuple[int, int]:
    with factory() as session:
        return (
            session.scalar(select(func.count()).select_from(Document)) or 0,
            session.scalar(select(func.count()).select_from(DocumentChunk)) or 0,
        )


def test_import_does_not_enter_rag_and_documentary_turn_still_works(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=True, min_score=-1.0)
    documents_before, chunks_before = _counts(env.factory)
    vectors_before = _vector_count(env.index, env.case_id)
    assert documents_before >= 2
    assert vectors_before >= 2

    service = QualysImportService(env.factory, env.settings)
    staged = service.stage_import(
        env.case_id,
        "valid.csv",
        (FIXTURES / "qualys_synthetic_valid.csv").read_bytes(),
    )
    service.confirm_import(env.case_id, staged.import_record.id)

    documents_after, chunks_after = _counts(env.factory)
    assert (documents_after, chunks_after) == (documents_before, chunks_before)
    assert _vector_count(env.index, env.case_id) == vectors_before

    generator = ScriptedGenerator(
        payloads=[
            AnswerPayload(answer="Hay 5 registros importados en la instantánea.", claims=[]),
            AnswerPayload(
                answer="El control EV.CU aplica cifrado en reposo.",
                claims=[
                    Claim(
                        text="El control EV.CU aplica cifrado en reposo.",
                        chunk_ids=[env.case_document.chunk_ids[0]],
                        quote="cifrado en reposo",
                    )
                ],
            ),
        ],
        decisions=[
            ToolDecision(use_findings=True, arguments={"origin": "imported"}),
            ToolDecision(use_findings=False, arguments={}),
        ],
    )

    imported_context = start_question_turn(
        env.factory,
        env.settings,
        scope=CaseScope(case_id=env.case_id),
        question="¿Cuántos registros importados hay?",
        generator=generator,
        embedder=FakeEmbedder(),
        index=env.index,
        token_counter=FakeTokenCounter(),
    )
    imported_result = execute_turn(imported_context)
    assert imported_result.outcome == "answered"
    with env.factory() as session:
        assert session.scalar(select(func.count()).select_from(MessageCitation)) == 0
        run = session.get(Run, imported_context.run_id)
        assert run is not None and run.tool_calls_count == 1
        call = session.scalar(select(RunToolCall).where(RunToolCall.run_id == run.id))
        assert call is not None and call.status == "ok"
        assert '"snapshot"' in (call.result_summary_json or "")
        assert '"items"' not in (call.result_summary_json or "")

    documentary_context = start_question_turn(
        env.factory,
        env.settings,
        scope=CaseScope(case_id=env.case_id),
        question="¿Qué control aplica cifrado en reposo?",
        generator=generator,
        embedder=FakeEmbedder(),
        index=env.index,
        token_counter=FakeTokenCounter(),
    )
    documentary_result = execute_turn(documentary_context)
    assert documentary_result.outcome == "answered"
    with env.factory() as session:
        citations = session.scalar(
            select(func.count())
            .select_from(MessageCitation)
            .where(MessageCitation.check_status == "valid")
        )
        assert (citations or 0) >= 1
    assert (documents_after, chunks_after) == (documents_before, chunks_before)
    assert _vector_count(env.index, env.case_id) == vectors_before
