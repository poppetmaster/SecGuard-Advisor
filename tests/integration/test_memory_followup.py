"""Integración de memoria: seguimiento con historial confirmado y citas nuevas."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from tests.fixtures.conversation import build_env
from tests.fixtures.fakes import FakeEmbedder, FakeTokenCounter, ScriptedGenerator

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.conversation.llm import AnswerPayload, Claim
from secguard_advisor.conversation.memory import open_memory
from secguard_advisor.conversation.turn import execute_turn, start_question_turn
from secguard_advisor.db.models import Conversation, Message, MessageCitation

pytestmark = pytest.mark.integration


def _payload(chunk_id: str, quote: str, answer: str) -> AnswerPayload:
    return AnswerPayload(
        answer=answer,
        claims=[Claim(text=answer, chunk_ids=[chunk_id], quote=quote)],
    )


def _ask(env, store, generator, question: str):
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
    return execute_turn(context, memory=store)


def _conversation_id(env) -> str:
    with env.factory() as session:
        return session.scalar(select(Conversation).where(Conversation.case_id == env.case_id)).id


def test_followup_uses_history_and_retrieves_new_evidence(tmp_path: Path) -> None:
    env = build_env(tmp_path, min_score=-1.0)
    store = open_memory(env.settings.checkpoints_path)
    public = env.public_document.chunk_ids[0]
    generator = ScriptedGenerator(
        [
            _payload(
                public,
                "seis funciones centrales",
                "El marco define seis funciones centrales.",
            ),
            _payload(
                public,
                "seis funciones centrales",
                "La función GOVERN encabeza las seis funciones.",
            ),
        ]
    )
    try:
        first = _ask(
            env,
            store,
            generator,
            "¿Cuáles son las seis funciones centrales del NIST CSF 2.0?",
        )
        second = _ask(
            env,
            store,
            generator,
            "De esas seis, explica GOVERN y cita el documento.",
        )

        assert first.outcome == "answered"
        assert second.outcome == "answered"
        assert "Conversación previa" in generator.prompts[1]
        assert "¿Cuáles son las seis funciones centrales" in generator.prompts[1]
        assert "El marco define seis funciones centrales." in generator.prompts[1]
        assert "no es evidencia" in generator.prompts[1].casefold()

        conversation_id = _conversation_id(env)
        with env.factory() as session:
            messages = list(
                session.scalars(
                    select(Message)
                    .where(Message.conversation_id == conversation_id)
                    .order_by(Message.seq)
                )
            )
            assert [(m.role, m.content) for m in messages[:2]] == [
                ("user", "¿Cuáles son las seis funciones centrales del NIST CSF 2.0?"),
                ("assistant", "El marco define seis funciones centrales."),
            ]
            citations = list(
                session.scalars(
                    select(MessageCitation).where(MessageCitation.check_status == "valid")
                )
            )
            assert len(citations) == 2
            assert citations[0].message_id != citations[1].message_id

        status, snapshot = store.read(conversation_id)
        assert status == "ok"
        assert snapshot is not None
        assert [turn.role for turn in snapshot.history] == [
            "user",
            "assistant",
            "user",
            "assistant",
        ]
    finally:
        store.close()
