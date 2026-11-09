"""Servicio de conversación: hilo único, secuencia e historial confirmado."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from secguard_advisor.conversation.memory import (
    HistoryTurn,
    MemoryStore,
    fingerprint,
)
from secguard_advisor.db.models import Conversation, Message, new_id

DEFAULT_MAX_MESSAGES = 8
DEFAULT_MAX_CHARS = 6000


def get_or_create_conversation(session: Session, case_id: str) -> Conversation:
    """Una conversación por caso; no se confirma la transacción del llamador."""
    conversation = session.scalar(select(Conversation).where(Conversation.case_id == case_id))
    if conversation is not None:
        return conversation
    conversation = Conversation(case_id=case_id, thread_id=new_id())
    session.add(conversation)
    session.flush()
    return conversation


def next_seq(session: Session, conversation_id: str) -> int:
    """Siguiente número de mensaje del hilo."""
    highest = session.scalar(
        select(func.max(Message.seq)).where(Message.conversation_id == conversation_id)
    )
    return (highest or 0) + 1


def create_question_message(session: Session, conversation_id: str, question: str) -> Message:
    """Inserta la pregunta del turno actual; no confirma la transacción."""
    message = Message(
        conversation_id=conversation_id,
        seq=next_seq(session, conversation_id),
        role="user",
        content=question,
        status="complete",
    )
    session.add(message)
    session.flush()
    return message


def load_confirmed_history(
    session: Session,
    conversation_id: str,
    *,
    exclude_message_id: str | None = None,
    max_messages: int = DEFAULT_MAX_MESSAGES,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> tuple[HistoryTurn, ...]:
    """Historial confirmado y acotado, con turnos completos y del más nuevo al más viejo.

    Los mensajes de la base de aplicación son la fuente autoritativa. La selección
    conserva los turnos más recientes que caben en los límites y nunca parte un
    par pregunta/respuesta.
    """
    if max_messages <= 0 or max_chars <= 0:
        return ()

    rows = list(
        session.scalars(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.role.in_(("user", "assistant")),
            )
            .order_by(Message.seq)
        )
    )

    pairs: list[tuple[HistoryTurn, HistoryTurn | None]] = []
    pending: HistoryTurn | None = None
    for message in rows:
        if message.id == exclude_message_id:
            continue
        turn = HistoryTurn(seq=message.seq, role=message.role, content=message.content)
        if message.role == "user":
            if pending is not None:
                pairs.append((pending, None))
            pending = turn
        elif pending is not None:
            pairs.append((pending, turn))
            pending = None
        # Un asistente sin pregunta previa no se puede atribuir: se descarta.
    if pending is not None:
        pairs.append((pending, None))

    selected: list[tuple[HistoryTurn, HistoryTurn | None]] = []
    message_count = 0
    char_count = 0
    for pair in reversed(pairs):
        pair_turns = [turn for turn in pair if turn is not None]
        size = len(pair_turns)
        chars = sum(len(turn.content) for turn in pair_turns)
        if message_count + size > max_messages or char_count + chars > max_chars:
            break
        selected.append(pair)
        message_count += size
        char_count += chars

    flattened: list[HistoryTurn] = []
    for pair in reversed(selected):
        flattened.extend(turn for turn in pair if turn is not None)
    return tuple(flattened)


def reconcile_memory(
    memory: MemoryStore,
    conversation_id: str,
    turns: tuple[HistoryTurn, ...],
) -> str:
    """Alinea el checkpoint con los mensajes confirmados.

    Devuelve ``current``, ``rebuilt_missing``, ``rebuilt_stale``,
    ``trimmed_ahead`` o ``rebuilt_foreign``. No hay atomicidad entre la base de
    aplicación y la de checkpoints: si el proceso muere entre ambas, la próxima
    reconciliación vuelve a alinear el checkpoint.
    """
    status, snapshot = memory.read(conversation_id)
    if status == "missing":
        result = "rebuilt_missing"
    elif status == "foreign":
        result = "rebuilt_foreign"
    elif snapshot is not None and snapshot.fingerprint == fingerprint(turns):
        return "current"
    elif snapshot is not None and len(snapshot.history) > len(turns):
        result = "trimmed_ahead"
    else:
        result = "rebuilt_stale"

    memory.write(conversation_id, turns)
    return result


def retrieval_query(question: str, turns: tuple[HistoryTurn, ...]) -> str:
    """Amplía la consulta de recuperación con la última pregunta confirmada.

    La conversación ayuda a interpretar referencias; la evidencia se recupera
    igual para la pregunta actual y no se reutilizan respuestas anteriores como
    fuentes.
    """
    previous = [turn.content for turn in turns if turn.role == "user"]
    if not previous:
        return question
    return f"{question}\nContexto previo: {previous[-1]}"
