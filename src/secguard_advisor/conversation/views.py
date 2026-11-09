"""Vistas de lectura de la conversación y de la evidencia de ejecución."""

from __future__ import annotations

from urllib.parse import quote as url_quote

from sqlalchemy import select
from sqlalchemy.orm import Session

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.db.models import (
    Conversation,
    Document,
    DocumentChunk,
    DocumentVersion,
    Message,
    MessageCitation,
    Run,
    RunSource,
    RunStep,
)

ORIGIN_LABELS = {
    "public_corpus": "Corpus público",
    "case_evidence": "Evidencia del caso",
}

CHECK_LABELS = {
    "valid": "válida",
    "rejected": "rechazada",
}

REVIEW_LABELS = {
    "unreviewed": "pendiente de revisión",
    "supported": "respaldada",
    "not_supported": "no respaldada",
}

RUN_STATUS_LABELS = {
    "running": "En curso",
    "succeeded": "Finalizada",
    "failed": "Fallida",
    "timeout": "Tiempo agotado",
    "interrupted": "Interrumpida",
}

OUTCOME_LABELS = {
    "answered": "Respondida con citas",
    "insufficient_evidence": "Información insuficiente",
    "abstained_invalid_citations": "Abstención por citas inválidas",
    "error": "Sin respuesta",
}


def _locator_url(case_id: str, citation: MessageCitation) -> str:
    base = (
        f"/cases/{case_id}/documents/{citation.document_id}"
        f"/versions/{citation.document_version_id}/fragments/{citation.chunk_id}"
    )
    return f"{base}?quote={url_quote(citation.quote)}&from=consultation"


def citation_view(session: Session, case_id: str, citation: MessageCitation) -> dict:
    document = session.get(Document, citation.document_id)
    version = session.get(DocumentVersion, citation.document_version_id)
    version_notice = None
    if document is not None and document.current_version_id not in {
        None,
        citation.document_version_id,
    }:
        version_notice = "Versión superada"
    return {
        "id": citation.id,
        "message_id": citation.message_id,
        "document_title": document.title if document else "Documento",
        "origin": document.origin if document else "case_evidence",
        "origin_label": ORIGIN_LABELS.get(
            document.origin if document else "case_evidence", "Evidencia"
        ),
        "version_label": version.declared_version if version else None,
        "page": citation.page,
        "section": citation.section,
        "quote": citation.quote,
        "locator": _locator_url(case_id, citation),
        "check_status": citation.check_status,
        "check_label": CHECK_LABELS.get(citation.check_status, citation.check_status),
        "check_reason": citation.check_reason,
        "version_notice": version_notice,
        "review_status": citation.support_review_status,
        "review_label": REVIEW_LABELS.get(
            citation.support_review_status, citation.support_review_status
        ),
        "reviewed_by": citation.support_reviewed_by,
        "reviewed_at": citation.support_reviewed_at,
        "review_note": citation.support_review_note,
        "is_supported": citation.support_review_status == "supported",
        "is_pending": citation.support_review_status == "unreviewed",
    }


def _sources_view(session: Session, run_id: str) -> list[dict]:
    rows = list(
        session.scalars(
            select(RunSource).where(RunSource.run_id == run_id).order_by(RunSource.rank)
        )
    )
    sources: list[dict] = []
    for row in rows:
        chunk = session.get(DocumentChunk, row.chunk_id)
        version = session.get(DocumentVersion, chunk.version_id) if chunk is not None else None
        document = session.get(Document, version.document_id) if version is not None else None
        sources.append(
            {
                "rank": row.rank,
                "origin": row.origin,
                "origin_label": ORIGIN_LABELS.get(row.origin, row.origin),
                "title": document.title if document else "Documento",
                "page": chunk.page_start if chunk else None,
                "section": chunk.section if chunk else None,
                "score": round(row.score, 4),
                "used_in_answer": row.used_in_answer,
            }
        )
    return sources


def _message_run(session: Session, message: Message) -> Run | None:
    if message.role == "user":
        return session.scalar(
            select(Run).where(Run.question_message_id == message.id).order_by(Run.attempt_no.desc())
        )
    if message.run_id:
        return session.get(Run, message.run_id)
    return None


def conversation_view(session: Session, scope: CaseScope, *, reviewer_configured: bool) -> dict:
    """Historial del caso con citas válidas, fuentes y ejecuciones."""
    conversation = session.scalar(select(Conversation).where(Conversation.case_id == scope.case_id))
    if conversation is None:
        return {
            "messages": [],
            "reviewer_configured": reviewer_configured,
            "has_conversation": False,
        }

    messages: list[dict] = []
    for message in session.scalars(
        select(Message).where(Message.conversation_id == conversation.id).order_by(Message.seq)
    ):
        run = _message_run(session, message)
        citations = [
            citation_view(session, scope.case_id, citation)
            for citation in session.scalars(
                select(MessageCitation)
                .where(MessageCitation.message_id == message.id)
                .order_by(MessageCitation.created_at)
            )
            if citation.check_status == "valid"
        ]
        messages.append(
            {
                "id": message.id,
                "role": message.role,
                "content": message.content,
                "created_at": message.created_at,
                "run_id": run.id if run else None,
                "run_status": run.status if run else None,
                "run_status_label": RUN_STATUS_LABELS.get(run.status if run else ""),
                "citations": citations,
                "sources": _sources_view(session, run.id) if run else [],
            }
        )
    return {
        "messages": messages,
        "reviewer_configured": reviewer_configured,
        "has_conversation": True,
    }


def latest_failed_run(session: Session, scope: CaseScope) -> Run | None:
    """Última ejecución reintentable del caso, para ofrecer el reintento."""
    return session.scalar(
        select(Run)
        .where(
            Run.case_id == scope.case_id,
            Run.status.in_(("failed", "timeout", "interrupted")),
            Run.answer_message_id.is_(None),
        )
        .order_by(Run.started_at.desc())
    )


def run_view(session: Session, scope: CaseScope, run_id: str) -> dict | None:
    """Evidencia de ejecución completa, siempre dentro del alcance del caso."""
    run = session.get(Run, run_id)
    if run is None or run.case_id != scope.case_id:
        return None
    question = session.get(Message, run.question_message_id) if run.question_message_id else None
    steps = list(
        session.scalars(select(RunStep).where(RunStep.run_id == run.id).order_by(RunStep.seq))
    )
    return {
        "id": run.id,
        "status": run.status,
        "status_label": RUN_STATUS_LABELS.get(run.status, run.status),
        "outcome": run.outcome,
        "outcome_label": OUTCOME_LABELS.get(run.outcome or ""),
        "attempt_no": run.attempt_no,
        "retry_of_run_id": run.retry_of_run_id,
        "question": question.content if question else None,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "duration_ms": run.duration_ms,
        "generator_model": run.generator_model,
        "generator_digest": run.generator_digest,
        "generator_num_ctx": run.generator_num_ctx,
        "generator_temperature": run.generator_temperature,
        "generator_seed": run.generator_seed,
        "embedding_model": run.embedding_model,
        "embedding_dim": run.embedding_dim,
        "prompt_version": run.prompt_version,
        "error_code": run.error_code,
        "error_message": run.error_message,
        "trace_status": run.trace_status,
        "steps": [
            {
                "seq": step.seq,
                "name": step.name,
                "origin": step.origin,
                "status": step.status,
                "duration_ms": step.duration_ms,
            }
            for step in steps
        ],
        "sources": _sources_view(session, run.id),
    }
