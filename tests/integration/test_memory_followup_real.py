"""Integración real de memoria: tres preguntas, reinicio y citas verificables."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from sqlalchemy import select
from tests.fixtures.corpus import create_case
from tests.fixtures.real_corpus import real_embedder

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.conversation.llm import GenerationConfig, OllamaGenerator
from secguard_advisor.conversation.memory import open_memory
from secguard_advisor.conversation.tokenizer import load_prompt_counter
from secguard_advisor.conversation.turn import execute_turn, start_question_turn
from secguard_advisor.corpus.ingest import ingest_public_corpus
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import (
    Conversation,
    DocumentChunk,
    Message,
    MessageCitation,
    Run,
)
from secguard_advisor.retrieval.index import ChromaIndex

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]
QUESTION_1 = "¿Cuáles son las seis funciones centrales del NIST Cybersecurity Framework 2.0?"
QUESTION_2 = "De esas seis, explica GOVERN y cita el documento."
QUESTION_3 = "¿Cuál de las funciones acabamos de profundizar?"


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        storage_dir=tmp_path / "storage",
        corpus_dir=tmp_path / "corpus",
    )


def _ingest_csf2(settings: Settings, factory) -> None:
    source = ROOT / "data" / "corpus" / "originals" / "csf2.pdf"
    manifest = json.loads((ROOT / "data" / "corpus" / "manifest.json").read_text("utf-8"))
    entry = next(item for item in manifest["sources"] if item["id"] == "csf2")
    originals = settings.corpus_dir / "originals"
    originals.mkdir(parents=True, exist_ok=True)
    shutil.copy(source, originals / "csf2.pdf")
    (settings.corpus_dir / "manifest.json").write_text(
        json.dumps({"schema_version": 1, "sources": [entry]}), encoding="utf-8"
    )
    embedder = real_embedder(settings)
    index = ChromaIndex(settings.chroma_dir)
    try:
        outcomes = ingest_public_corpus(factory, settings, embedder=embedder, index=index)
    finally:
        embedder.close()
    assert [outcome.status for outcome in outcomes] == ["created"]


def _generator(settings: Settings) -> OllamaGenerator:
    return OllamaGenerator(
        GenerationConfig(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            num_ctx=settings.generator_num_ctx,
            temperature=settings.generator_temperature,
            seed=settings.generator_seed,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    )


def _ask(settings, factory, index, store, case_id, embedder, generator, question):
    context = start_question_turn(
        factory,
        settings,
        scope=CaseScope(case_id=case_id),
        question=question,
        generator=generator,
        embedder=embedder,
        index=index,
        token_counter=load_prompt_counter(settings.ollama_model),
    )
    return context, execute_turn(context, memory=store)


def _answer_state(factory, message_id: str) -> tuple[str, int]:
    with factory() as session:
        message = session.get(Message, message_id)
        citations = list(
            session.scalars(
                select(MessageCitation).where(
                    MessageCitation.message_id == message_id,
                    MessageCitation.check_status == "valid",
                )
            )
        )
        return message.content, len(citations)


def test_three_questions_keep_context_with_real_generation(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        case_id = create_case(session, "Memoria real")
        session.commit()
    _ingest_csf2(settings, factory)

    store = open_memory(settings.checkpoints_path)
    embedder = real_embedder(settings)
    index = ChromaIndex(settings.chroma_dir)
    try:
        first_context, first = _ask(
            settings, factory, index, store, case_id, embedder, _generator(settings), QUESTION_1
        )
        assert first.outcome == "answered", "la primera respuesta no tuvo citas válidas"
        with factory() as session:
            first_answer_id = session.get(Run, first_context.run_id).answer_message_id
        first_text, first_citations = _answer_state(factory, first_answer_id)
        assert first_citations >= 1

        second_context, second = _ask(
            settings, factory, index, store, case_id, embedder, _generator(settings), QUESTION_2
        )
        assert second.outcome == "answered", "la segunda respuesta no tuvo citas válidas"
        with factory() as session:
            answer_id = session.get(Run, second_context.run_id).answer_message_id
        second_text, second_citations = _answer_state(factory, answer_id)
        assert second_citations >= 1
        assert "govern" in second_text.casefold()

        conversation_id = _conversation_id(factory, case_id)
        with factory() as session:
            assert (
                session.scalar(
                    select(Message)
                    .where(Message.conversation_id == conversation_id)
                    .order_by(Message.seq.desc())
                ).seq
                == 4
            )

        # Reinicio: se cierran memoria y motor y se abren de nuevo sobre el mismo
        # almacenamiento; el historial confirmado sigue en la base de negocio.
        store.close()
        engine.dispose()
        engine = create_engine_for_url(settings.database_url)
        factory = create_session_factory(engine)
        store = open_memory(settings.checkpoints_path)
        index = ChromaIndex(settings.chroma_dir)

        third_context, third = _ask(
            settings, factory, index, store, case_id, embedder, _generator(settings), QUESTION_3
        )
        assert third.outcome == "answered", "la pregunta de seguimiento no usó el contexto"
        with factory() as session:
            answer_id = session.get(Run, third_context.run_id).answer_message_id
        third_text, third_citations = _answer_state(factory, answer_id)
        assert third_citations >= 1
        assert "govern" in third_text.casefold()

        with factory() as session:
            messages = list(
                session.scalars(
                    select(Message)
                    .where(Message.conversation_id == conversation_id)
                    .order_by(Message.seq)
                )
            )
            assert [(message.role, message.seq) for message in messages] == [
                ("user", 1),
                ("assistant", 2),
                ("user", 3),
                ("assistant", 4),
                ("user", 5),
                ("assistant", 6),
            ]
            succeeded = list(
                session.scalars(
                    select(Run).where(Run.case_id == case_id, Run.status == "succeeded")
                )
            )
            assert len(succeeded) == 3
            chunks = session.scalars(
                select(MessageCitation).where(MessageCitation.check_status == "valid")
            )
            assert all(session.get(DocumentChunk, citation.chunk_id) for citation in chunks)
        print("Q1:", first_text[:120])
        print("Q2:", second_text[:120])
        print("Q3:", third_text[:120])
    finally:
        store.close()
        embedder.close()
        engine.dispose()


def _conversation_id(factory, case_id: str) -> str:
    with factory() as session:
        return session.scalar(select(Conversation).where(Conversation.case_id == case_id)).id
