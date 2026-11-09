"""Integración real: respuesta con cita comprobable sobre el corpus oficial."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from tests.fixtures.corpus import create_case
from tests.fixtures.real_corpus import ingest_one_public_source, real_embedder

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.conversation.llm import GenerationConfig, OllamaGenerator
from secguard_advisor.conversation.tokenizer import load_prompt_counter
from secguard_advisor.conversation.turn import execute_turn, start_question_turn
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import (
    Document,
    DocumentChunk,
    DocumentVersion,
    Message,
    MessageCitation,
)
from secguard_advisor.retrieval.citations import normalize_for_match
from secguard_advisor.retrieval.index import ChromaIndex

pytestmark = pytest.mark.integration

QUESTION = "¿Cuáles son las seis funciones centrales del NIST Cybersecurity Framework 2.0?"


def test_real_answer_cites_a_locatable_fragment(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, storage_dir=tmp_path / "storage")
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)

    with factory() as session:
        case_id = create_case(session, "Caso de respuesta real")
        session.commit()

    ingest_one_public_source(settings, factory)

    generator = OllamaGenerator(
        GenerationConfig(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            num_ctx=settings.generator_num_ctx,
            temperature=settings.generator_temperature,
            seed=settings.generator_seed,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    )
    embedder = real_embedder(settings)
    index = ChromaIndex(settings.chroma_dir)
    try:
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
        assert result.outcome == "answered", "el modelo no produjo citas válidas"

        with factory() as session:
            answer = session.scalar(
                select(Message).where(Message.role == "assistant").order_by(Message.seq.desc())
            )
            assert answer is not None
            assert answer.content.strip()
            citations = list(
                session.scalars(
                    select(MessageCitation).where(
                        MessageCitation.message_id == answer.id,
                        MessageCitation.check_status == "valid",
                    )
                )
            )
            assert citations, "la respuesta no tiene citas válidas"

            for citation in citations:
                chunk = session.get(DocumentChunk, citation.chunk_id)
                version = session.get(DocumentVersion, citation.document_version_id)
                document = session.get(Document, citation.document_id)
                assert chunk is not None
                assert version is not None and version.id == chunk.version_id
                assert document is not None and document.origin == "public_corpus"
                assert normalize_for_match(citation.quote) in normalize_for_match(chunk.text)
                assert citation.page == chunk.page_start
                assert citation.locator == chunk.locator
                print(
                    "CITA:",
                    document.title,
                    "|",
                    version.declared_version,
                    "| página",
                    citation.page,
                    "|",
                    citation.locator,
                    "|",
                    citation.quote[:120],
                )
    finally:
        embedder.close()
        engine.dispose()
