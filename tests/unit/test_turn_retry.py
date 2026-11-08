"""Pruebas del reintento de turno sobre la pregunta existente."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from tests.fixtures.conversation import build_env
from tests.fixtures.fakes import FakeEmbedder, ScriptedGenerator

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.conversation.concurrency import GenerationSlot
from secguard_advisor.conversation.llm import AnswerPayload, Claim, ModelUnavailable
from secguard_advisor.conversation.retry import (
    RetryNotAllowed,
    RunNotFound,
    plan_retry,
    start_retry_turn,
)
from secguard_advisor.conversation.turn import execute_turn, start_question_turn
from secguard_advisor.conversation.views import latest_failed_run
from secguard_advisor.db.models import Case, Conversation, Message, Run, new_id
from secguard_advisor.web.app import create_app

ORIGIN = {"Origin": "http://testserver"}
HTMX = {**ORIGIN, "HX-Request": "true"}


def _failed_turn(env):
    context = start_question_turn(
        env.factory,
        env.settings,
        scope=CaseScope(case_id=env.case_id),
        question="¿Qué controles aplican?",
        generator=ScriptedGenerator(error=ModelUnavailable("caído")),
        embedder=FakeEmbedder(),
        index=env.index,
    )
    result = execute_turn(context)
    assert result.status == "failed"
    return context.run_id


def test_retry_reuses_question_and_creates_new_attempt(tmp_path: Path) -> None:
    env = build_env(tmp_path)
    failed_run_id = _failed_turn(env)

    plan = plan_retry(env.factory, CaseScope(case_id=env.case_id), failed_run_id)
    assert plan.attempt_no == 2

    generator = ScriptedGenerator(
        [
            AnswerPayload(
                answer="El marco define seis funciones.",
                claims=[
                    Claim(
                        text="Afirmación",
                        chunk_ids=[env.public_document.chunk_ids[0]],
                        quote="seis funciones centrales",
                    )
                ],
            )
        ]
    )
    context = start_retry_turn(
        env.factory,
        env.settings,
        scope=CaseScope(case_id=env.case_id),
        run_id=failed_run_id,
        generator=generator,
        embedder=FakeEmbedder(),
        index=env.index,
    )
    result = execute_turn(context)

    assert result.outcome == "answered"
    with env.factory() as session:
        runs = list(
            session.scalars(select(Run).where(Run.case_id == env.case_id).order_by(Run.attempt_no))
        )
        assert [run.attempt_no for run in runs] == [1, 2]
        assert runs[1].retry_of_run_id == failed_run_id
        assert runs[1].question_message_id == runs[0].question_message_id
        assert (
            session.scalar(select(func.count()).select_from(Message).where(Message.role == "user"))
            == 1
        )
        assert session.scalar(select(func.count()).select_from(Message)) == 2


def test_retry_is_rejected_when_answer_exists(tmp_path: Path) -> None:
    env = build_env(tmp_path)
    generator = ScriptedGenerator(
        [
            AnswerPayload(
                answer="El marco define seis funciones.",
                claims=[
                    Claim(
                        text="Afirmación",
                        chunk_ids=[env.public_document.chunk_ids[0]],
                        quote="seis funciones centrales",
                    )
                ],
            )
        ]
    )
    context = start_question_turn(
        env.factory,
        env.settings,
        scope=CaseScope(case_id=env.case_id),
        question="¿Qué controles aplican?",
        generator=generator,
        embedder=FakeEmbedder(),
        index=env.index,
    )
    execute_turn(context)

    with pytest.raises(RetryNotAllowed):
        plan_retry(env.factory, CaseScope(case_id=env.case_id), context.run_id)


def test_retry_rejects_running_run(tmp_path: Path) -> None:
    env = build_env(tmp_path)
    with env.factory() as session:
        case = session.get(Case, env.case_id)
        conversation = Conversation(case_id=case.id, thread_id=new_id())
        session.add(conversation)
        session.flush()
        question = Message(
            conversation_id=conversation.id,
            seq=1,
            role="user",
            content="pregunta",
            status="complete",
        )
        session.add(question)
        session.flush()
        run = Run(
            case_id=case.id,
            conversation_id=conversation.id,
            question_message_id=question.id,
            status="running",
            generator_model="fake",
            generator_num_ctx=8192,
            generator_temperature=0.1,
            embedding_model="fake-embedding",
            embedding_dim=4,
            prompt_version="chat-v1",
        )
        session.add(run)
        session.commit()
        run_id = run.id

    with pytest.raises(RetryNotAllowed):
        plan_retry(env.factory, CaseScope(case_id=env.case_id), run_id)


def test_retry_of_another_case_is_not_found(tmp_path: Path) -> None:
    env = build_env(tmp_path)
    failed_run_id = _failed_turn(env)
    with env.factory() as session:
        other = Case(title="Otro caso", synthetic_notice="Escenario educativo")
        session.add(other)
        session.commit()
        other_id = other.id

    with pytest.raises(RunNotFound):
        plan_retry(env.factory, CaseScope(case_id=other_id), failed_run_id)


def test_retry_route_returns_429_when_global_slot_is_busy(tmp_path: Path) -> None:
    env = build_env(tmp_path)
    failed_run_id = _failed_turn(env)
    slot = GenerationSlot(timeout_seconds=0.05)
    app = create_app(
        env.settings,
        ollama_probe=lambda: True,
        embedder_factory=lambda: FakeEmbedder(),
        index_factory=lambda: env.index,
        llm_factory=lambda: ScriptedGenerator(payloads=[]),
        generation_slot=slot,
    )
    assert slot.acquire() is True
    try:
        with TestClient(app) as client:
            response = client.post(
                f"/cases/{env.case_id}/runs/{failed_run_id}/retry",
                headers=HTMX,
            )
    finally:
        slot.release()

    assert response.status_code == 429
    with env.factory() as session:
        assert session.scalar(select(func.count()).select_from(Run)) == 1


def test_latest_failed_run_is_offered(tmp_path: Path) -> None:
    env = build_env(tmp_path)
    failed_run_id = _failed_turn(env)

    with env.factory() as session:
        run = latest_failed_run(session, CaseScope(case_id=env.case_id))

    assert run is not None
    assert run.id == failed_run_id
    assert run.status == "failed"
