"""Pruebas de persistencia de la conversación y reutilización de la pregunta."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select
from tests.fixtures.corpus import create_case

from secguard_advisor.conversation import service as service_module
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import Conversation, Message


@pytest.fixture
def factory(tmp_path: Path):
    engine = create_engine_for_url(f"sqlite:///{tmp_path / 'conversation.sqlite3'}")
    Base.metadata.create_all(engine)
    yield create_session_factory(engine)
    engine.dispose()


def _case(factory, title: str) -> str:
    with factory() as session:
        case_id = create_case(session, title)
        session.commit()
        return case_id


def test_one_conversation_per_case(factory) -> None:
    case_id = _case(factory, "Caso único")
    other_id = _case(factory, "Otro caso")

    with factory() as session:
        first = service_module.get_or_create_conversation(session, case_id)
        session.commit()
        second = service_module.get_or_create_conversation(session, case_id)
        session.commit()
        other = service_module.get_or_create_conversation(session, other_id)
        session.commit()

    assert first.id == second.id
    assert first.id != other.id
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Conversation)) == 2


def test_sequence_is_contiguous_and_uses_the_max(factory) -> None:
    case_id = _case(factory, "Caso de secuencia")
    with factory() as session:
        conversation = service_module.get_or_create_conversation(session, case_id)
        session.flush()
        assert service_module.next_seq(session, conversation.id) == 1
        session.add(
            Message(
                conversation_id=conversation.id,
                seq=1,
                role="user",
                content="pregunta",
                status="complete",
            )
        )
        session.commit()
        assert service_module.next_seq(session, conversation.id) == 2


def test_question_message_is_persisted_with_its_sequence(factory) -> None:
    case_id = _case(factory, "Caso de pregunta")
    with factory() as session:
        conversation = service_module.get_or_create_conversation(session, case_id)
        session.flush()
        question = service_module.create_question_message(
            session, conversation.id, "¿Qué exige la norma?"
        )
        session.commit()
        question_id = question.id

    with factory() as session:
        stored = session.get(Message, question_id)
        assert stored.seq == 1
        assert stored.role == "user"
        assert stored.status == "complete"
        assert stored.content == "¿Qué exige la norma?"


def test_retry_excludes_the_current_question_from_history(factory) -> None:
    case_id = _case(factory, "Caso de reintento")
    with factory() as session:
        conversation = service_module.get_or_create_conversation(session, case_id)
        session.flush()
        first = service_module.create_question_message(session, conversation.id, "anterior")
        session.flush()
        session.add(
            Message(
                conversation_id=conversation.id,
                seq=3,
                role="assistant",
                content="respuesta anterior",
                status="complete",
            )
        )
        retried = service_module.create_question_message(session, conversation.id, "reintentada")
        session.commit()
        conversation_id = conversation.id
        retried_id = retried.id

    with factory() as session:
        turns = service_module.load_confirmed_history(
            session, conversation_id, exclude_message_id=retried_id
        )

    assert [turn.content for turn in turns] == ["anterior", "respuesta anterior"]
    assert all(turn.content != "reintentada" for turn in turns)
    assert first.id != retried_id


def test_history_never_returns_messages_from_another_case(factory) -> None:
    case_a = _case(factory, "Caso A")
    case_b = _case(factory, "Caso B")
    with factory() as session:
        conversation_a = service_module.get_or_create_conversation(session, case_a)
        conversation_b = service_module.get_or_create_conversation(session, case_b)
        session.flush()
        session.add(
            Message(
                conversation_id=conversation_b.id,
                seq=1,
                role="user",
                content="marca exclusiva del caso B",
                status="complete",
            )
        )
        session.commit()
        conversation_a_id = conversation_a.id

    with factory() as session:
        turns = service_module.load_confirmed_history(session, conversation_a_id)

    assert turns == ()


def test_retrieval_query_adds_only_confirmed_context(factory) -> None:
    turns = (
        service_module.HistoryTurn(1, "user", "¿Cuáles son las seis funciones del CSF?"),
        service_module.HistoryTurn(2, "assistant", "GOVERN, IDENTIFY, PROTECT, DETECT…"),
    )

    query = service_module.retrieval_query("¿Cuál acabamos de profundizar?", turns)

    assert query.startswith("¿Cuál acabamos de profundizar?")
    assert "seis funciones del CSF" in query
    assert "GOVERN, IDENTIFY" not in query
    assert service_module.retrieval_query("¿Cuál acabamos de profundizar?", ()) == (
        "¿Cuál acabamos de profundizar?"
    )
