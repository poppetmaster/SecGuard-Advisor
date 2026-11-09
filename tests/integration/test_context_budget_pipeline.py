"""Integración del presupuesto: reducción, reparación y fallo controlado."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import func, select
from tests.fixtures.conversation import build_env
from tests.fixtures.fakes import FakeEmbedder, FakeTokenCounter, ScriptedGenerator

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.conversation import service
from secguard_advisor.conversation.llm import AnswerPayload, Claim
from secguard_advisor.conversation.retry import plan_retry
from secguard_advisor.conversation.turn import execute_turn, start_question_turn
from secguard_advisor.db.models import Conversation, Message, MessageCitation, Run, RunStep

pytestmark = pytest.mark.integration


def _payload(chunk_id: str, quote: str, answer: str = "Respuesta documentada.") -> AnswerPayload:
    return AnswerPayload(
        answer=answer,
        claims=[Claim(text=answer, chunk_ids=[chunk_id], quote=quote)],
    )


def _seed_history(factory, case_id: str, pairs: int, size: int) -> None:
    with factory() as session:
        conversation = service.get_or_create_conversation(session, case_id)
        for index in range(1, pairs + 1):
            session.add(
                Message(
                    conversation_id=conversation.id,
                    seq=index * 2 - 1,
                    role="user",
                    content=f"pregunta {index} " + "q" * size,
                    status="complete",
                )
            )
            session.add(
                Message(
                    conversation_id=conversation.id,
                    seq=index * 2,
                    role="assistant",
                    content=f"respuesta {index} " + "a" * size,
                    status="complete",
                )
            )
        session.commit()


def _ask(env, generator, question: str):
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
    return context, execute_turn(context)


def _step_detail(factory, run_id: str, name: str) -> dict:
    with factory() as session:
        step = session.scalar(select(RunStep).where(RunStep.run_id == run_id, RunStep.name == name))
        assert step is not None and step.detail_json is not None
        return json.loads(step.detail_json)


def _history_snapshot(factory, case_id: str) -> list[tuple[int, str, str]]:
    with factory() as session:
        conversation = session.scalar(select(Conversation).where(Conversation.case_id == case_id))
        rows = session.scalars(
            select(Message).where(Message.conversation_id == conversation.id).order_by(Message.seq)
        )
        return [(message.seq, message.role, message.content) for message in rows]


def test_prompt_is_bounded_and_persisted_history_is_untouched(tmp_path: Path) -> None:
    env = build_env(
        tmp_path,
        min_score=-1.0,
        settings_overrides={
            "generator_num_ctx": 4200,
            "history_max_messages": 10,
            "history_max_chars": 20000,
        },
    )
    _seed_history(env.factory, env.case_id, pairs=5, size=1500)
    before = _history_snapshot(env.factory, env.case_id)
    public = env.public_document.chunk_ids[0]
    generator = ScriptedGenerator(
        [_payload(public, "seis funciones centrales", "El marco define seis funciones.")]
    )

    context, result = _ask(env, generator, "¿Cuáles son las seis funciones?")

    assert result.outcome == "answered"
    detail = _step_detail(env.factory, context.run_id, "agent")
    assert detail["admitted_tokens"] <= detail["limit"]
    assert detail["dropped_history_messages"] > 0
    assert detail["dropped_sources"] == 0
    assert "pregunta 1 " not in generator.prompts[0]
    assert "seis funciones centrales" in generator.prompts[0]

    after = _history_snapshot(env.factory, env.case_id)
    assert after[: len(before)] == before
    assert len(after) == len(before) + 2


def test_repair_prompt_is_also_bounded(tmp_path: Path) -> None:
    env = build_env(
        tmp_path,
        min_score=-1.0,
        settings_overrides={
            "generator_num_ctx": 4200,
            "history_max_messages": 10,
            "history_max_chars": 20000,
        },
    )
    _seed_history(env.factory, env.case_id, pairs=5, size=1500)
    public = env.public_document.chunk_ids[0]
    generator = ScriptedGenerator(
        [
            _payload(public, "texto parafraseado", "El marco define seis funciones."),
            _payload(public, "seis funciones centrales", "El marco define seis funciones."),
        ]
    )

    context, result = _ask(env, generator, "¿Cuáles son las seis funciones?")

    assert result.outcome == "answered"
    assert generator.calls == 2
    for name in ("agent", "repair"):
        detail = _step_detail(env.factory, context.run_id, name)
        assert detail["admitted_tokens"] <= detail["limit"]
    assert _step_detail(env.factory, context.run_id, "repair")["dropped_history_messages"] > 0


def test_minimal_content_that_does_not_fit_fails_without_generating(tmp_path: Path) -> None:
    env = build_env(
        tmp_path,
        min_score=-1.0,
        settings_overrides={"generator_num_ctx": 900},
    )
    generator = ScriptedGenerator([])

    context, result = _ask(env, generator, "¿Cabe en el contexto?")

    assert result.status == "failed"
    assert result.error_code == "context_budget_exceeded"
    assert result.http_status == 500
    assert generator.calls == 0
    with env.factory() as session:
        assert session.scalar(select(func.count()).select_from(MessageCitation)) == 0
        run = session.get(Run, context.run_id)
        assert run.status == "failed"
        assert run.error_code == "context_budget_exceeded"
        assert run.answer_message_id is None
    plan = plan_retry(env.factory, CaseScope(case_id=env.case_id), context.run_id)
    assert plan.question == "¿Cabe en el contexto?"
