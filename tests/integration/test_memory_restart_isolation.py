"""Integración: memoria tras reiniciar y aislamiento entre dos casos."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select
from tests.fixtures.conversation import CASE_TEXT, build_env
from tests.fixtures.corpus import create_case, seed_document
from tests.fixtures.fakes import FakeEmbedder, FakeTokenCounter, ScriptedGenerator

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.conversation.llm import AnswerPayload, Claim
from secguard_advisor.conversation.memory import open_memory
from secguard_advisor.conversation.turn import execute_turn, start_question_turn
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import Conversation, Message, Run
from secguard_advisor.retrieval.index import ChromaIndex

pytestmark = pytest.mark.integration

B_TEXT = "MARCA-B-EXCLUSIVA: el activo secreto del caso B usa doble factor."


def _payload(chunk_id: str, quote: str, answer: str) -> AnswerPayload:
    return AnswerPayload(
        answer=answer,
        claims=[Claim(text=answer, chunk_ids=[chunk_id], quote=quote)],
    )


def _ask(settings, factory, index, store, case_id, generator, question: str):
    context = start_question_turn(
        factory,
        settings,
        scope=CaseScope(case_id=case_id),
        question=question,
        generator=generator,
        embedder=FakeEmbedder(),
        index=index,
        token_counter=FakeTokenCounter(),
    )
    return execute_turn(context, memory=store)


def _counts(factory, case_id: str) -> tuple[int, int]:
    with factory() as session:
        conversation = session.scalar(select(Conversation).where(Conversation.case_id == case_id))
        messages = session.scalar(
            select(func.count())
            .select_from(Message)
            .where(Message.conversation_id == conversation.id)
        )
        runs = session.scalar(select(func.count()).select_from(Run).where(Run.case_id == case_id))
        return messages, runs


def test_restart_keeps_history_and_context(tmp_path: Path) -> None:
    env = build_env(tmp_path, min_score=-1.0)
    index = env.index
    store = open_memory(env.settings.checkpoints_path)
    public = env.public_document.chunk_ids[0]
    try:
        first = _ask(
            env.settings,
            env.factory,
            index,
            store,
            env.case_id,
            ScriptedGenerator(
                [_payload(public, "seis funciones centrales", "El marco define seis funciones.")]
            ),
            "¿Cuáles son las seis funciones centrales del NIST CSF 2.0?",
        )
        assert first.outcome == "answered"
        assert _counts(env.factory, env.case_id) == (2, 1)

        # Reinicio: se cierran la memoria y el motor, y se abren de nuevo sobre el
        # mismo almacenamiento. El historial confirmado vive en la base de negocio.
        store.close()
        new_engine = create_engine_for_url(env.settings.database_url)
        new_factory = create_session_factory(new_engine)
        new_store = open_memory(env.settings.checkpoints_path)
        new_index = ChromaIndex(env.settings.chroma_dir)
        try:
            generator = ScriptedGenerator(
                [_payload(public, "seis funciones centrales", "Acabamos de profundizar GOVERN.")]
            )
            second = _ask(
                env.settings,
                new_factory,
                new_index,
                new_store,
                env.case_id,
                generator,
                "¿Cuál de las funciones acabamos de profundizar?",
            )

            assert second.outcome == "answered"
            assert _counts(new_factory, env.case_id) == (4, 2)
            assert "Conversación previa" in generator.prompts[0]
            assert "¿Cuáles son las seis funciones centrales" in generator.prompts[0]
            assert "El marco define seis funciones." in generator.prompts[0]

            conversation_id = _conversation_id(new_factory, env.case_id)
            with new_factory() as session:
                messages = list(
                    session.scalars(
                        select(Message)
                        .where(Message.conversation_id == conversation_id)
                        .order_by(Message.seq)
                    )
                )
            assert [message.seq for message in messages] == [1, 2, 3, 4]
            assert [message.role for message in messages] == [
                "user",
                "assistant",
                "user",
                "assistant",
            ]
            status, snapshot = new_store.read(conversation_id)
            assert status == "ok"
            assert snapshot is not None and len(snapshot.history) == 4
        finally:
            new_store.close()
            new_engine.dispose()
    finally:
        store.close()


def test_two_cases_keep_separate_context(tmp_path: Path) -> None:
    env = build_env(tmp_path, min_score=-1.0)
    store = open_memory(env.settings.checkpoints_path)
    with env.factory() as session:
        case_b = create_case(session, "Caso B")
        session.commit()
    document_b = seed_document(
        env.factory,
        texts=[B_TEXT],
        index=env.index,
        embedder=FakeEmbedder(),
        case_id=case_b,
        title="Evidencia del caso B",
        pages=[1],
    )
    try:
        generator_a = ScriptedGenerator(
            [
                _payload(
                    env.case_document.chunk_ids[0],
                    "cifrado en reposo",
                    "La política interna exige cifrado en reposo.",
                )
            ]
        )
        _ask(
            env.settings,
            env.factory,
            env.index,
            store,
            env.case_id,
            generator_a,
            "¿Qué control aplica la política interna?",
        )
        generator_b = ScriptedGenerator(
            [_payload(document_b.chunk_ids[0], "doble factor", "El caso B usa doble factor.")]
        )
        _ask(
            env.settings,
            env.factory,
            env.index,
            store,
            case_b,
            generator_b,
            "¿Qué protección usa el activo del caso B?",
        )

        assert "MARCA-B-EXCLUSIVA" not in generator_a.prompts[0]
        assert CASE_TEXT not in generator_b.prompts[0]
        assert "Conversación previa" not in generator_b.prompts[0]

        conversation_a = _conversation_id(env.factory, env.case_id)
        conversation_b = _conversation_id(env.factory, case_b)
        assert conversation_a != conversation_b
        status_a, snapshot_a = store.read(conversation_a)
        status_b, snapshot_b = store.read(conversation_b)
        assert status_a == status_b == "ok"
        assert all("MARCA-B" not in turn.content for turn in snapshot_a.history)
        assert all(turn.content != CASE_TEXT for turn in snapshot_b.history)
        with env.factory() as session:
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(Message)
                    .where(Message.conversation_id == conversation_a)
                )
                == 2
            )
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(Message)
                    .where(Message.conversation_id == conversation_b)
                )
                == 2
            )
    finally:
        store.close()


def _conversation_id(factory, case_id: str) -> str:
    with factory() as session:
        return session.scalar(select(Conversation).where(Conversation.case_id == case_id)).id
