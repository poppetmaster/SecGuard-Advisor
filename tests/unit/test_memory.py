"""Pruebas de la memoria operativa: checkpoints, historial y reconciliación."""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.fixtures.corpus import create_case

from secguard_advisor.config import Settings
from secguard_advisor.conversation import memory as memory_module
from secguard_advisor.conversation import service as service_module
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import Conversation, Message, new_id


@pytest.fixture
def context(tmp_path: Path):
    settings = Settings(_env_file=None, storage_dir=tmp_path / "storage")
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    store = memory_module.open_memory(settings.checkpoints_path)
    yield settings, factory, store
    store.close()
    engine.dispose()


def _conversation(factory, title: str = "Caso") -> tuple[str, str]:
    with factory() as session:
        case_id = create_case(session, title)
        conversation = Conversation(case_id=case_id, thread_id=new_id())
        session.add(conversation)
        session.commit()
        return case_id, conversation.id


def _add_turn(factory, conversation_id: str, question: str, answer: str, seq: int):
    with factory() as session:
        session.add(
            Message(
                conversation_id=conversation_id,
                seq=seq,
                role="user",
                content=question,
                status="complete",
            )
        )
        session.add(
            Message(
                conversation_id=conversation_id,
                seq=seq + 1,
                role="assistant",
                content=answer,
                status="complete",
            )
        )
        session.commit()


def test_snapshot_is_keyed_by_conversation(context) -> None:
    _settings, factory, store = context
    _case, conversation_id = _conversation(factory)
    _case_b, other_id = _conversation(factory, "Otro caso")

    store.write(conversation_id, (memory_module.HistoryTurn(1, "user", "hola"),))

    status, snapshot = store.read(conversation_id)
    assert status == "ok"
    assert snapshot is not None
    assert snapshot.owner == conversation_id
    assert snapshot.history[0].content == "hola"

    other_status, other_snapshot = store.read(other_id)
    assert other_status == "missing"
    assert other_snapshot is None


def test_foreign_snapshot_is_rejected(context) -> None:
    _settings, factory, store = context
    _case, conversation_id = _conversation(factory)

    store.write_snapshot(
        conversation_id,
        memory_module.MemorySnapshot(
            owner="conversation-ajena",
            history=(memory_module.HistoryTurn(1, "user", "secreto ajeno"),),
            fingerprint="1:1",
        ),
    )

    status, snapshot = store.read(conversation_id)

    assert status == "foreign"
    assert snapshot is None


def test_confirmed_history_is_rebuilt_from_messages(context) -> None:
    _settings, factory, _store = context
    _case, conversation_id = _conversation(factory)
    _add_turn(factory, conversation_id, "primera pregunta", "primera respuesta", 1)

    with factory() as session:
        turns = service_module.load_confirmed_history(session, conversation_id)

    assert [turn.role for turn in turns] == ["user", "assistant"]
    assert [turn.content for turn in turns] == ["primera pregunta", "primera respuesta"]


def test_confirmed_history_excludes_the_current_question(context) -> None:
    _settings, factory, _store = context
    _case, conversation_id = _conversation(factory)
    _add_turn(factory, conversation_id, "anterior", "respuesta anterior", 1)
    with factory() as session:
        current = Message(
            conversation_id=conversation_id,
            seq=3,
            role="user",
            content="pregunta actual",
            status="complete",
        )
        session.add(current)
        session.commit()
        current_id = current.id

    with factory() as session:
        turns = service_module.load_confirmed_history(
            session, conversation_id, exclude_message_id=current_id
        )

    assert [turn.content for turn in turns] == ["anterior", "respuesta anterior"]


def test_history_is_bounded_by_messages_and_characters(context) -> None:
    _settings, factory, _store = context
    _case, conversation_id = _conversation(factory)
    for index in range(1, 7):
        _add_turn(
            factory,
            conversation_id,
            f"pregunta {index}",
            f"respuesta {index} " + ("x" * 100),
            index * 2 - 1,
        )

    with factory() as session:
        by_messages = service_module.load_confirmed_history(
            session, conversation_id, max_messages=4, max_chars=100_000
        )
        by_chars = service_module.load_confirmed_history(
            session, conversation_id, max_messages=8, max_chars=260
        )

    assert [turn.content for turn in by_messages[:2]] == ["pregunta 5", "respuesta 5 " + "x" * 100]
    assert len(by_messages) == 4
    assert all(turn.content != "pregunta 1" for turn in by_messages)
    assert len(by_chars) == 4
    assert all(turn.content != "pregunta 4" for turn in by_chars)


def test_history_keeps_whole_turns_only(context) -> None:
    _settings, factory, _store = context
    _case, conversation_id = _conversation(factory)
    _add_turn(factory, conversation_id, "pregunta", "r" * 400, 1)

    with factory() as session:
        turns = service_module.load_confirmed_history(
            session, conversation_id, max_messages=8, max_chars=100
        )

    assert turns == ()


def test_fingerprint_identifies_the_last_confirmed_message(context) -> None:
    first = (memory_module.HistoryTurn(1, "user", "a"),)
    second = (
        memory_module.HistoryTurn(1, "user", "a"),
        memory_module.HistoryTurn(2, "assistant", "b"),
    )

    assert memory_module.fingerprint(first) != memory_module.fingerprint(second)
    assert memory_module.fingerprint(()) == "empty"


def test_reconcile_missing_stale_ahead_and_foreign(context) -> None:
    _settings, factory, store = context
    _case, conversation_id = _conversation(factory)
    _add_turn(factory, conversation_id, "pregunta", "respuesta", 1)
    with factory() as session:
        turns = service_module.load_confirmed_history(session, conversation_id)

    assert service_module.reconcile_memory(store, conversation_id, turns) == "rebuilt_missing"
    assert store.read(conversation_id)[0] == "ok"
    assert service_module.reconcile_memory(store, conversation_id, turns) == "current"

    store.write(
        conversation_id,
        (
            memory_module.HistoryTurn(1, "user", "pregunta"),
            memory_module.HistoryTurn(2, "assistant", "respuesta"),
            memory_module.HistoryTurn(3, "assistant", "sobrante"),
        ),
    )
    assert service_module.reconcile_memory(store, conversation_id, turns) == "trimmed_ahead"

    store.write(conversation_id, (memory_module.HistoryTurn(1, "user", "pregunta"),))
    assert service_module.reconcile_memory(store, conversation_id, turns) == "rebuilt_stale"

    store.write_snapshot(
        conversation_id,
        memory_module.MemorySnapshot(
            owner="conversation-ajena",
            history=(),
            fingerprint="empty",
        ),
    )
    assert service_module.reconcile_memory(store, conversation_id, turns) == "rebuilt_foreign"
    assert store.read(conversation_id)[0] == "ok"


def test_reconciliation_never_mixes_conversations(context) -> None:
    _settings, factory, store = context
    case_a, conversation_a = _conversation(factory, "Caso A")
    _case_b, conversation_b = _conversation(factory, "Caso B")
    with factory() as session:
        session.add(
            Message(
                conversation_id=conversation_b,
                seq=1,
                role="user",
                content="dato exclusivo del caso B",
                status="complete",
            )
        )
        session.commit()
    with factory() as session:
        turns_a = service_module.load_confirmed_history(session, conversation_a)

    service_module.reconcile_memory(store, conversation_a, turns_a)
    _status, snapshot = store.read(conversation_a)

    assert snapshot is not None
    assert all("caso B" not in turn.content for turn in snapshot.history)
    assert case_a
