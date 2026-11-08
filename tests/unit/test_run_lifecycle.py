"""Pruebas del ciclo de vida de ejecución."""

from pathlib import Path

import pytest

from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import Case, Conversation, Message, Run, new_id
from secguard_advisor.evidence.runs import (
    ActiveRunConflict,
    DuplicateAttempt,
    close_run,
    create_run,
)


@pytest.fixture
def factory(tmp_path: Path):
    engine = create_engine_for_url(f"sqlite:///{tmp_path / 'runs.sqlite3'}")
    Base.metadata.create_all(engine)
    yield create_session_factory(engine)
    engine.dispose()


def _context(session):
    case = Case(title="Caso", synthetic_notice="Escenario educativo sintético")
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
    return case, conversation, question


def _create(session, case, conversation, question, attempt_no: int = 1) -> Run:
    return create_run(
        session,
        case_id=case.id,
        conversation_id=conversation.id,
        question_message_id=question.id,
        generator_model="qwen3.5:9b",
        generator_num_ctx=8192,
        generator_temperature=0.1,
        embedding_model="embeddinggemma",
        embedding_dim=768,
        prompt_version="chat-v1",
        attempt_no=attempt_no,
    )


def test_create_and_conflict(factory) -> None:
    with factory() as session:
        case, conversation, question = _context(session)
        run = _create(session, case, conversation, question)
        session.commit()

        assert run.status == "running"
        assert run.attempt_no == 1

        other_question = Message(
            conversation_id=conversation.id,
            seq=2,
            role="user",
            content="otra",
            status="complete",
        )
        session.add(other_question)
        session.flush()

        with pytest.raises(ActiveRunConflict):
            _create(session, case, conversation, other_question)


def test_close_does_not_commit_by_itself(factory) -> None:
    with factory() as session:
        case, conversation, question = _context(session)
        run = _create(session, case, conversation, question)
        session.commit()
        run_id = run.id

        close_run(
            session,
            run,
            status="succeeded",
            outcome="answered",
            duration_ms=10,
        )
        session.rollback()

    with factory() as session:
        stored = session.get(Run, run_id)
        assert stored is not None
        assert stored.status == "running"
        assert stored.finished_at is None


def test_close_persists_answer_and_status(factory) -> None:
    with factory() as session:
        case, conversation, question = _context(session)
        run = _create(session, case, conversation, question)
        session.commit()
        answer = Message(
            conversation_id=conversation.id,
            seq=2,
            role="assistant",
            content="respuesta",
            status="complete",
        )
        session.add(answer)
        session.flush()

        close_run(
            session,
            run,
            status="succeeded",
            outcome="answered",
            duration_ms=12,
            answer_message_id=answer.id,
        )
        session.commit()
        run_id = run.id

    with factory() as session:
        stored = session.get(Run, run_id)
        assert stored is not None
        assert stored.status == "succeeded"
        assert stored.answer_message_id == answer.id
        assert stored.finished_at is not None


def test_duplicate_attempt_is_rejected(factory) -> None:
    with factory() as session:
        case, conversation, question = _context(session)
        run = _create(session, case, conversation, question)
        session.commit()
        close_run(session, run, status="failed", outcome="error")
        session.commit()

        with pytest.raises(DuplicateAttempt):
            _create(session, case, conversation, question, attempt_no=1)


def test_invalid_close_status_is_rejected(factory) -> None:
    with factory() as session:
        case, conversation, question = _context(session)
        run = _create(session, case, conversation, question)

        with pytest.raises(ValueError):
            close_run(session, run, status="unknown")
