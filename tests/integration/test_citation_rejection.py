"""Integración: una cita inválida se descarta y queda registrada con su motivo."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from tests.fixtures.corpus import create_case
from tests.fixtures.fakes import ScriptedGenerator
from tests.fixtures.real_corpus import ingest_one_public_source, real_embedder

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.conversation.llm import AnswerPayload, Claim
from secguard_advisor.conversation.tokenizer import load_prompt_counter
from secguard_advisor.conversation.turn import execute_turn, start_question_turn
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import Message, MessageCitation, Run
from secguard_advisor.retrieval.index import ChromaIndex
from secguard_advisor.retrieval.search import search_documents

pytestmark = pytest.mark.integration

QUESTION = "¿Cuáles son las seis funciones centrales del NIST Cybersecurity Framework 2.0?"


def _paraphrase(chunk_id: str) -> AnswerPayload:
    return AnswerPayload(
        answer="El marco define seis funciones centrales.",
        claims=[
            Claim(
                text="El marco define seis funciones centrales para organizar resultados.",
                chunk_ids=[chunk_id],
                quote="el marco describe seis funciones para ordenar los resultados",
            )
        ],
    )


def test_paraphrased_quote_is_rejected_and_recorded(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, storage_dir=tmp_path / "storage")
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)

    with factory() as session:
        case_id = create_case(session, "Caso de cita inválida")
        session.commit()

    ingest_one_public_source(settings, factory)
    embedder = real_embedder(settings)
    index = ChromaIndex(settings.chroma_dir)
    try:
        with factory() as session:
            retrieval = search_documents(
                session,
                scope=CaseScope(case_id=case_id),
                query=QUESTION,
                embedder=embedder,
                index=index,
                top_k=settings.retrieval_top_k,
                min_score=settings.retrieval_min_score,
            )
        assert retrieval.hits, "la recuperación real no devolvió candidatos"
        target_chunk_id = retrieval.hits[0].chunk_id

        generator = ScriptedGenerator(
            payloads=[_paraphrase(target_chunk_id), _paraphrase(target_chunk_id)]
        )
        context = start_question_turn(
            factory,
            settings,
            scope=CaseScope(case_id=case_id),
            question=QUESTION,
            generator=generator,
            embedder=embedder,
            index=index,
            token_counter=load_prompt_counter(settings.ollama_model),
        )
        result = execute_turn(context)

        assert result.status == "succeeded"
        assert result.outcome == "abstained_invalid_citations"
        assert generator.calls == 2

        with factory() as session:
            run = session.scalar(select(Run).where(Run.case_id == case_id))
            assert run is not None
            assert run.outcome == "abstained_invalid_citations"
            answer = session.scalar(select(Message).where(Message.role == "assistant"))
            assert answer is not None
            citations = list(
                session.scalars(
                    select(MessageCitation).where(MessageCitation.message_id == answer.id)
                )
            )
            assert citations
            assert all(citation.check_status == "rejected" for citation in citations)
            assert all(citation.check_reason == "quote_not_found" for citation in citations)
    finally:
        embedder.close()
        engine.dispose()
