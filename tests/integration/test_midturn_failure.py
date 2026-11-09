"""Integración: fallo a mitad de turno, reintento y reconciliación del checkpoint."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import func, select
from tests.fixtures.conversation import build_env
from tests.fixtures.fakes import FakeEmbedder, FakeTokenCounter, ScriptedGenerator

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.conversation import nodes
from secguard_advisor.conversation.llm import AnswerPayload, Claim
from secguard_advisor.conversation.memory import HistoryTurn, open_memory
from secguard_advisor.conversation.retry import plan_retry, start_retry_turn
from secguard_advisor.conversation.turn import execute_turn, start_question_turn
from secguard_advisor.db.models import (
    Conversation,
    Message,
    MessageCitation,
    Run,
    RunStep,
)

pytestmark = pytest.mark.integration


def _payload(chunk_id: str, answer: str) -> AnswerPayload:
    return AnswerPayload(
        answer=answer,
        claims=[Claim(text=answer, chunk_ids=[chunk_id], quote="seis funciones centrales")],
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
    return context, execute_turn(context, memory=store)


def _conversation_id(env) -> str:
    with env.factory() as session:
        return session.scalar(select(Conversation).where(Conversation.case_id == env.case_id)).id


def test_final_transaction_failure_leaves_no_answer_and_allows_retry(
    tmp_path: Path, monkeypatch
) -> None:
    env = build_env(tmp_path, min_score=-1.0)
    store = open_memory(env.settings.checkpoints_path)
    public = env.public_document.chunk_ids[0]
    original = nodes.persist_turn

    def broken(*_args, **_kwargs):
        raise RuntimeError("fallo controlado de la transacción final")

    monkeypatch.setattr(nodes, "persist_turn", broken)
    try:
        context, result = _ask(
            env,
            store,
            ScriptedGenerator([_payload(public, "El marco define seis funciones.")]),
            "¿Qué funciones define el marco?",
        )

        assert result.status == "failed"
        assert result.error_code == "internal_error"
        with env.factory() as session:
            messages = list(
                session.scalars(
                    select(Message)
                    .where(Message.conversation_id == context.conversation_id)
                    .order_by(Message.seq)
                )
            )
            assert [(m.role, m.content) for m in messages] == [
                ("user", "¿Qué funciones define el marco?")
            ]
            assert session.scalar(select(func.count()).select_from(MessageCitation)) == 0
            run = session.get(Run, context.run_id)
            assert run.status == "failed"
            assert run.answer_message_id is None
            plan = plan_retry(env.factory, CaseScope(case_id=env.case_id), context.run_id)
            assert plan.attempt_no == 2
            assert plan.question == "¿Qué funciones define el marco?"
    finally:
        monkeypatch.setattr(nodes, "persist_turn", original)

    with env.factory() as session:
        run_id = session.scalar(select(Run.id).where(Run.case_id == env.case_id))
    retry_context = start_retry_turn(
        env.factory,
        env.settings,
        scope=CaseScope(case_id=env.case_id),
        run_id=run_id,
        generator=ScriptedGenerator([_payload(public, "El marco define seis funciones.")]),
        embedder=FakeEmbedder(),
        index=env.index,
        token_counter=FakeTokenCounter(),
    )
    retry = execute_turn(retry_context, memory=store)
    try:
        assert retry.outcome == "answered"
        with env.factory() as session:
            runs = list(
                session.scalars(
                    select(Run).where(Run.case_id == env.case_id).order_by(Run.attempt_no)
                )
            )
            assert [run.attempt_no for run in runs] == [1, 2]
            assert runs[1].retry_of_run_id == runs[0].id
            assert runs[1].question_message_id == runs[0].question_message_id
            assert session.scalar(select(func.count()).select_from(Message)) == 2
            assert (
                session.scalar(
                    select(func.count()).select_from(Message).where(Message.role == "user")
                )
                == 1
            )
            assert session.scalar(select(func.count()).select_from(MessageCitation)) == 1
    finally:
        store.close()


def test_checkpoint_ahead_is_trimmed_and_stale_is_rebuilt(tmp_path: Path) -> None:
    env = build_env(tmp_path, min_score=-1.0)
    store = open_memory(env.settings.checkpoints_path)
    public = env.public_document.chunk_ids[0]
    try:
        _ask(
            env,
            store,
            ScriptedGenerator([_payload(public, "El marco define seis funciones.")]),
            "¿Cuáles son las seis funciones centrales?",
        )
        conversation_id = _conversation_id(env)

        store.write(
            conversation_id,
            (
                HistoryTurn(1, "user", "¿Cuáles son las seis funciones centrales?"),
                HistoryTurn(2, "assistant", "El marco define seis funciones."),
                HistoryTurn(3, "assistant", "sobrante que no está en la base"),
            ),
        )
        generator = ScriptedGenerator([_payload(public, "GOVERN encabeza las funciones.")])
        context, result = _ask(
            env,
            store,
            generator,
            "¿Cuál de las funciones acabamos de profundizar?",
        )

        assert result.outcome == "answered"
        assert "sobrante que no está en la base" not in generator.prompts[0]
        assert "El marco define seis funciones." in generator.prompts[0]
        with env.factory() as session:
            step = session.scalar(
                select(RunStep).where(
                    RunStep.run_id == context.run_id, RunStep.name == "load_memory"
                )
            )
            assert step is not None
            assert json.loads(step.detail_json)["memory"] == "trimmed_ahead"

        store.write(
            conversation_id,
            (HistoryTurn(1, "user", "solo un turno"),),
        )
        generator = ScriptedGenerator([_payload(public, "GOVERN encabeza las funciones.")])
        third_context, third = _ask(
            env,
            store,
            generator,
            "¿Qué función gobierna?",
        )

        assert third.outcome == "answered"
        with env.factory() as session:
            step = session.scalar(
                select(RunStep).where(
                    RunStep.run_id == third_context.run_id, RunStep.name == "load_memory"
                )
            )
            assert json.loads(step.detail_json)["memory"] == "rebuilt_stale"
            messages = list(
                session.scalars(
                    select(Message)
                    .where(Message.conversation_id == conversation_id)
                    .order_by(Message.seq)
                )
            )
            assert [message.seq for message in messages] == [1, 2, 3, 4, 5, 6]
            assert [message.role for message in messages] == [
                "user",
                "assistant",
                "user",
                "assistant",
                "user",
                "assistant",
            ]
    finally:
        store.close()
