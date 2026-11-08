"""Persistencia atómica de la respuesta, las citas y el cierre de ejecución."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from secguard_advisor.db.models import (
    Message,
    MessageCitation,
    Run,
    RunSource,
    RunStep,
    utc_now_iso,
)
from secguard_advisor.evidence.runs import close_run


@dataclass(frozen=True, slots=True)
class CitationDraft:
    """Cita construida por la ejecución, válida o rechazada."""

    chunk_id: str
    document_id: str
    version_id: str
    page: int | None
    section: str | None
    quote: str
    locator: str
    check_status: str
    check_reason: str | None


@dataclass(frozen=True, slots=True)
class StepRecord:
    """Paso de la ejecución listo para persistir."""

    name: str
    origin: str
    status: str
    duration_ms: int
    detail: dict | None = None


def next_message_seq(session: Session, conversation_id: str) -> int:
    """Siguiente número de mensaje del hilo, dentro de la transacción del llamador."""
    highest = session.scalar(
        select(func.max(Message.seq)).where(Message.conversation_id == conversation_id)
    )
    return (highest or 0) + 1


def _write_steps(session: Session, run_id: str, steps: tuple[StepRecord, ...]) -> None:
    for position, step in enumerate(steps, start=1):
        session.add(
            RunStep(
                run_id=run_id,
                seq=position,
                name=step.name,
                origin=step.origin,
                status=step.status,
                duration_ms=step.duration_ms,
                detail_json=_json_detail(step.detail),
            )
        )


def _json_detail(detail: dict | None) -> str | None:
    if not detail:
        return None
    import json

    return json.dumps(detail, ensure_ascii=False)


def persist_turn(
    factory: sessionmaker[Session],
    *,
    run_id: str,
    answer_text: str,
    citations: tuple[CitationDraft, ...],
    rejected: tuple[CitationDraft, ...] = (),
    hits: tuple = (),
    steps: tuple[StepRecord, ...],
    outcome: str,
    duration_ms: int,
) -> str:
    """Guarda respuesta, citas, fuentes, pasos y cierre en una sola transacción."""
    with factory() as session:
        run = session.get(Run, run_id)
        if run is None:
            raise LookupError("La ejecución no existe.")

        message = Message(
            conversation_id=run.conversation_id,
            seq=next_message_seq(session, run.conversation_id),
            role="assistant",
            content=answer_text,
            status="complete",
            run_id=run.id,
        )
        session.add(message)
        session.flush()

        valid_chunk_ids = set()
        for draft in tuple(citations) + tuple(rejected):
            if draft.check_status == "valid":
                valid_chunk_ids.add(draft.chunk_id)
            session.add(
                MessageCitation(
                    message_id=message.id,
                    chunk_id=draft.chunk_id,
                    document_id=draft.document_id,
                    document_version_id=draft.version_id,
                    page=draft.page,
                    section=draft.section,
                    quote=draft.quote,
                    locator=draft.locator,
                    check_status=draft.check_status,
                    check_reason=draft.check_reason,
                )
            )

        for rank, hit in enumerate(hits, start=1):
            session.add(
                RunSource(
                    run_id=run.id,
                    chunk_id=hit.chunk_id,
                    origin=hit.origin,
                    rank=rank,
                    score=hit.score,
                    used_in_answer=hit.chunk_id in valid_chunk_ids,
                )
            )

        _write_steps(session, run.id, steps)
        close_run(
            session,
            run,
            status="succeeded",
            outcome=outcome,
            duration_ms=duration_ms,
            answer_message_id=message.id,
        )
        run.steps_count = len(steps)
        run.tool_calls_count = 0
        session.commit()
        return message.id


def fail_run(
    factory: sessionmaker[Session],
    *,
    run_id: str,
    status: str,
    error_code: str,
    error_message: str,
    duration_ms: int,
    steps: tuple[StepRecord, ...] = (),
) -> None:
    """Cierra una ejecución fallida en una transacción corta, sin respuesta."""
    with factory() as session:
        run = session.get(Run, run_id)
        if run is None:
            return
        if steps:
            _write_steps(session, run.id, steps)
            run.steps_count = len(steps)
        close_run(
            session,
            run,
            status=status,
            outcome="error",
            duration_ms=duration_ms,
            error_code=error_code,
            error_message=error_message,
        )
        session.commit()


def utc_stamp() -> str:
    return utc_now_iso()
