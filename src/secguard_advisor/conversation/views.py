"""Vistas de lectura de la conversación y de la evidencia de ejecución."""

from __future__ import annotations

from urllib.parse import quote as url_quote

from sqlalchemy import select
from sqlalchemy.orm import Session

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.db.models import (
    Conversation,
    Document,
    DocumentVersion,
    Message,
    MessageCitation,
    Run,
)
from secguard_advisor.evidence.runs import (
    ORIGIN_LABELS,
    retry_allowed,
    serialize_attempts,
    serialize_steps,
)
from secguard_advisor.evidence.runs import (
    serialize_sources as _sources_view,
)
from secguard_advisor.evidence.runs import (
    serialize_tool_calls as tool_calls_view,
)

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


def _message_run(session: Session, message: Message) -> Run | None:
    if message.role == "user":
        return session.scalar(
            select(Run).where(Run.question_message_id == message.id).order_by(Run.attempt_no.desc())
        )
    if message.run_id:
        return session.get(Run, message.run_id)
    return None


def conversation_view(
    session: Session,
    scope: CaseScope,
    *,
    reviewer_configured: bool,
    factory=None,
) -> dict:
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
                "tool_calls": (
                    tool_calls_view(session, run.id, factory=factory, scope=scope) if run else []
                ),
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


TRACE_STATUS_LABELS = {
    "disabled": "No configurada",
    "submitted": "Enviada (no verificada)",
    "failed": "No disponible",
    "confirmed": "Verificada",
}

STEP_LABELS = {
    "load_scope": "Alcance del caso",
    "load_memory": "Memoria",
    "retrieve": "Recuperación documental",
    "decide": "Decisión de herramienta",
    "tools": "Herramienta",
    "agent": "Generación",
    "validate": "Control automático de citas",
    "repair": "Reparación",
    "abstain": "Abstención",
    "persist": "Persistencia",
}


def _budget_view(steps: list[dict]) -> list[dict]:
    """Extrae solo las mediciones de contexto realmente registradas."""
    budget: list[dict] = []
    for step in steps:
        detail = step.get("detail") or {}
        if not any(
            key in detail
            for key in ("admitted_tokens", "observed_prompt_tokens", "limit", "estimated_tokens")
        ):
            continue
        counter = detail.get("counter") or {}
        budget.append(
            {
                "step": step["name"],
                "admitted_tokens": detail.get("admitted_tokens"),
                "observed_prompt_tokens": detail.get("observed_prompt_tokens"),
                "estimated_tokens": detail.get("estimated_tokens"),
                "limit": detail.get("limit"),
                "output_reserve": detail.get("output_reserve"),
                "safety_margin": detail.get("safety_margin"),
                "history_messages": detail.get("history_messages"),
                "sources": detail.get("sources"),
                "method": counter.get("method"),
                "model": counter.get("model"),
                "template": counter.get("template"),
            }
        )
    return budget


def run_view(session: Session, scope: CaseScope, run_id: str, *, factory=None) -> dict | None:
    """Evidencia de ejecución completa, siempre dentro del alcance del caso."""
    run = session.get(Run, run_id)
    if run is None or run.case_id != scope.case_id:
        return None
    question = session.get(Message, run.question_message_id) if run.question_message_id else None
    steps = serialize_steps(session, run.id)
    attempts = [
        {
            **item,
            "status_label": RUN_STATUS_LABELS.get(item["status"], item["status"]),
            "outcome_label": OUTCOME_LABELS.get(item["outcome"] or "", item["outcome"]),
        }
        for item in serialize_attempts(session, run)
    ]
    previous = next((item for item in attempts if item["attempt_no"] == run.attempt_no - 1), None)
    citations: list[dict] = []
    rejected_reasons: list[str] = []
    if run.answer_message_id:
        citations = [
            citation_view(session, scope.case_id, citation)
            for citation in session.scalars(
                select(MessageCitation)
                .where(MessageCitation.message_id == run.answer_message_id)
                .order_by(MessageCitation.created_at)
            )
            if citation.check_status == "valid"
        ]
    validate_step = next((step for step in steps if step["name"] == "validate"), None)
    if validate_step and validate_step.get("detail"):
        rejected_reasons = list(validate_step["detail"].get("reasons") or [])
    tool_calls = tool_calls_view(session, run.id, factory=factory, scope=scope)
    tool_evidence = any(call["status"] == "ok" for call in tool_calls)
    budget = _budget_view(steps)
    return {
        "id": run.id,
        "status": run.status,
        "status_label": RUN_STATUS_LABELS.get(run.status, run.status),
        "outcome": run.outcome,
        "outcome_label": OUTCOME_LABELS.get(run.outcome or ""),
        "attempt_no": run.attempt_no,
        "retry_of_run_id": run.retry_of_run_id,
        "attempts": attempts,
        "previous_attempt": previous,
        "can_retry": retry_allowed(run),
        "retry_url": f"/cases/{scope.case_id}/runs/{run.id}/retry",
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
        "trace_status_label": TRACE_STATUS_LABELS.get(run.trace_status, run.trace_status),
        "trace_id": run.trace_id,
        "trace_url": run.trace_url,
        "steps": [
            {
                **step,
                "label": STEP_LABELS.get(step["name"], step["name"]),
            }
            for step in steps
        ],
        "sources": _sources_view(session, run.id),
        "tool_calls": tool_calls,
        "citations": citations,
        "rejected_reasons": rejected_reasons,
        "reviewed_count": sum(1 for item in citations if not item["is_pending"]),
        "pending_review_count": sum(1 for item in citations if item["is_pending"]),
        "budget": budget,
        "has_documentary_evidence": bool(citations),
        "has_tool_evidence": tool_evidence,
    }
