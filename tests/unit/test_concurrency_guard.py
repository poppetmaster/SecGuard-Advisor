"""Pruebas de los controles de concurrencia del turno."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from secguard_advisor.conversation.concurrency import GenerationSlot, find_active_run
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import Case, Conversation, Message, new_id
from secguard_advisor.evidence.runs import ActiveRunConflict, create_run


@pytest.fixture
def factory(tmp_path: Path):
    engine = create_engine_for_url(f"sqlite:///{tmp_path / 'concurrency.sqlite3'}")
    Base.metadata.create_all(engine)
    yield create_session_factory(engine)
    engine.dispose()


def _case_with_question(factory, title: str):
    with factory() as session:
        case = Case(title=title, synthetic_notice="Escenario educativo")
        session.add(case)
        session.flush()
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
        session.commit()
        return case.id, conversation.id, question.id


def _start(factory, case_id: str, conversation_id: str, question_id: str):
    with factory() as session:
        run = create_run(
            session,
            case_id=case_id,
            conversation_id=conversation_id,
            question_message_id=question_id,
            generator_model="fake",
            generator_num_ctx=8192,
            generator_temperature=0.1,
            embedding_model="fake-embedding",
            embedding_dim=4,
            prompt_version="chat-v1",
        )
        session.commit()
        return run.id


def test_second_conversation_in_same_case_is_rejected(factory) -> None:
    case_id, conversation_id, question_id = _case_with_question(factory, "Caso A")
    _start(factory, case_id, conversation_id, question_id)

    with factory() as session, pytest.raises(ActiveRunConflict):
        create_run(
            session,
            case_id=case_id,
            conversation_id=conversation_id,
            question_message_id=question_id,
            generator_model="fake",
            generator_num_ctx=8192,
            generator_temperature=0.1,
            embedding_model="fake-embedding",
            embedding_dim=4,
            prompt_version="chat-v1",
        )


def test_two_cases_can_start_independently(factory) -> None:
    case_a, conversation_a, question_a = _case_with_question(factory, "Caso A")
    case_b, conversation_b, question_b = _case_with_question(factory, "Caso B")

    _start(factory, case_a, conversation_a, question_a)
    _start(factory, case_b, conversation_b, question_b)

    with factory() as session:
        assert find_active_run(session, case_a) is not None
        assert find_active_run(session, case_b) is not None


def test_global_slot_allows_one_generation_and_times_out() -> None:
    slot = GenerationSlot(timeout_seconds=0.05)

    assert slot.acquire() is True
    started = threading.Event()
    finished = threading.Event()

    def contender() -> None:
        started.set()
        assert slot.acquire() is False
        finished.set()

    thread = threading.Thread(target=contender)
    thread.start()
    started.wait(timeout=1)
    assert finished.wait(timeout=2)

    slot.release()
    thread.join(timeout=1)
    assert slot.acquire() is True
    slot.release()


def test_slot_is_released_only_after_real_completion() -> None:
    slot = GenerationSlot(timeout_seconds=0.05)
    checked = threading.Event()

    assert slot.acquire() is True

    def second_query_while_running() -> None:
        assert slot.acquire() is False
        checked.set()

    thread = threading.Thread(target=second_query_while_running)
    thread.start()
    assert checked.wait(timeout=2)
    thread.join(timeout=1)

    slot.release()
    assert slot.acquire() is True
    slot.release()
