"""Revisión humana del respaldo semántico de una cita."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.db.models import Conversation, Message, MessageCitation, utc_now_iso

REVIEW_STATUSES = {"supported", "not_supported"}
MAX_NOTE_CHARS = 500


class ReviewNotConfigured(RuntimeError):
    """No hay identidad declarada de revisor."""


class CitationNotFound(LookupError):
    """La cita o el mensaje no existen en el caso autorizado."""


class ReviewNotAllowed(RuntimeError):
    """La cita no admite revisión en su estado actual."""


def review_citation(
    session: Session,
    scope: CaseScope,
    *,
    message_id: str,
    citation_id: str,
    status: str,
    note: str | None,
    reviewer_name: str | None,
) -> MessageCitation:
    """Registra la revisión humana de una cita válida del caso."""
    name = (reviewer_name or "").strip()
    if not name:
        raise ReviewNotConfigured("Configurá SECGUARD_REVIEWER_NAME para registrar una revisión.")
    if status not in REVIEW_STATUSES:
        raise ValueError("El estado de revisión no es válido.")
    cleaned_note = (note or "").strip() or None
    if cleaned_note is not None and len(cleaned_note) > MAX_NOTE_CHARS:
        raise ValueError("La observación supera los 500 caracteres.")

    message = session.get(Message, message_id)
    if message is None:
        raise CitationNotFound(message_id)
    conversation = session.get(Conversation, message.conversation_id)
    if conversation is None or conversation.case_id != scope.case_id:
        raise CitationNotFound(message_id)

    citation = session.scalar(
        select(MessageCitation).where(
            MessageCitation.id == citation_id,
            MessageCitation.message_id == message.id,
        )
    )
    if citation is None:
        raise CitationNotFound(citation_id)
    if citation.check_status != "valid":
        raise ReviewNotAllowed(
            "La cita no superó el control automático y no admite respaldo semántico."
        )

    citation.support_review_status = status
    citation.support_reviewed_by = name
    citation.support_reviewed_at = utc_now_iso()
    citation.support_review_note = cleaned_note
    session.add(citation)
    session.flush()
    return citation
