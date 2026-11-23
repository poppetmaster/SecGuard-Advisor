"""Notification events, components, attempts and idempotency."""

from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from secguard_advisor.db.models import (
    ContactChannel,
    NotificationAttempt,
    NotificationComponent,
    NotificationEvent,
    ReportVersion,
    utc_now_iso,
)
from secguard_advisor.notifications.contacts import mask_chat_id
from secguard_advisor.notifications.errors import NotificationError
from secguard_advisor.notifications.manifest import build_recipient_manifest
from secguard_advisor.reports.canonical import canonical_json, canonical_sha256

COMPONENT_KINDS = ("summary", "document")
EVENT_STATUSES = (
    "prepared",
    "queued",
    "sending",
    "accepted",
    "partial",
    "failed",
    "uncertain",
    "skipped",
)
COMPONENT_STATUSES = ("prepared", "requested", "accepted", "failed", "uncertain", "skipped")

EVENT_LABELS = {
    "prepared": "Preparado",
    "queued": "En cola",
    "sending": "Enviando",
    "accepted": "Aceptado por Telegram",
    "partial": "Parcial",
    "failed": "Fallido",
    "uncertain": "Incierto",
    "skipped": "Omitido",
}
MODE_LABELS = {"manual": "Manual", "automatic": "Automático"}
COMPONENT_LABELS = {
    "prepared": "Preparado",
    "requested": "Solicitado",
    "accepted": "Aceptado",
    "failed": "Fallido",
    "uncertain": "Incierto",
    "skipped": "Omitido",
}
ERROR_LABELS = {
    "contact_unverified": "Destinatario sin verificar o inactivo",
    "consent_missing": "Sin consentimiento vigente",
    "case_not_authorized": "Sin autorización para el caso",
    "manifest_mismatch": "El contenido o los destinatarios cambiaron",
    "pdf_integrity_mismatch": "El PDF no coincide con el aprobado",
    "document_render_failed": "PDF no disponible",
    "summary_failed": "El resumen no se envió",
    "component_revalidation_failed": "Destinatario o contenido inválido",
    "interrupted": "Interrumpido; requiere revisión",
    "timeout": "Sin respuesta; requiere revisión",
    "invalid_request": "Telegram rechazó la solicitud",
    "forbidden": "Telegram rechazó el destino",
    "rate_limited": "Límite de Telegram",
    "provider_error": "Error del proveedor; requiere revisión",
}


def idempotency_key(case_id: str, version_id: str, contact_id: str) -> str:
    return hashlib.sha256(f"{case_id}:{version_id}:{contact_id}".encode()).hexdigest()


def content_hash(manifest: dict[str, Any]) -> str:
    return canonical_sha256(
        {
            "outbound_text": manifest["outbound_text"],
            "pdf_sha256": manifest["pdf_sha256"],
            "content_policy": manifest["content_policy"],
        }
    )


def ensure_event(
    session: Session,
    *,
    version: ReportVersion,
    contact: ContactChannel,
    manifest: dict[str, Any],
    mode: str,
    confirmed_by: str | None = None,
    confirmed_at: str | None = None,
    confirmation_id: str | None = None,
    rule_id: str | None = None,
    rule_version: int | None = None,
) -> tuple[NotificationEvent, bool]:
    """Create the per-recipient event idempotently from the approved set manifest.

    Creation never grants permission to execute: execution claims each component separately.
    """
    key = idempotency_key(version.case_id, version.id, contact.id)
    existing = session.scalar(
        select(NotificationEvent).where(NotificationEvent.idempotency_key == key)
    )
    if existing is not None:
        if mode == "manual" and confirmation_id and existing.confirmation_id != confirmation_id:
            states = components(session, existing.id)
            if all(row.status in {"prepared", "failed", "skipped"} for row in states.values()):
                recipient_manifest = build_recipient_manifest(
                    session,
                    version,
                    contact.id,
                    approved_recipients_sha256=manifest["recipients_sha256"],
                )
                existing.confirmation_id = confirmation_id
                existing.manifest_json = canonical_json(recipient_manifest)
                existing.manifest_sha256 = recipient_manifest["manifest_sha256"]
                existing.content_policy_json = canonical_json(recipient_manifest["content_policy"])
                existing.content_sha256 = content_hash(recipient_manifest)
                existing.status = "prepared"
                session.flush()
        return existing, False
    recipient_manifest = build_recipient_manifest(
        session,
        version,
        contact.id,
        approved_recipients_sha256=manifest["recipients_sha256"],
    )
    event = NotificationEvent(
        case_id=version.case_id,
        report_version_id=version.id,
        contact_id=contact.id,
        mode=mode,
        rule_id=rule_id,
        rule_version=rule_version,
        confirmation_id=confirmation_id,
        idempotency_key=key,
        manifest_json=canonical_json(recipient_manifest),
        manifest_sha256=recipient_manifest["manifest_sha256"],
        content_policy_json=canonical_json(recipient_manifest["content_policy"]),
        content_sha256=content_hash(recipient_manifest),
        confirmed_by=confirmed_by,
        confirmed_at=confirmed_at,
        status="prepared",
    )
    session.add(event)
    session.flush()
    for kind in COMPONENT_KINDS:
        session.add(
            NotificationComponent(
                event_id=event.id,
                kind=kind,
                status="prepared",
                attempt_count=0,
            )
        )
    session.flush()
    return event, True


def components(session: Session, event_id: str) -> dict[str, NotificationComponent]:
    rows = session.scalars(
        select(NotificationComponent).where(NotificationComponent.event_id == event_id)
    )
    return {row.kind: row for row in rows}


def claim_component(
    session: Session, *, event: NotificationEvent, kind: str
) -> NotificationAttempt | None:
    """Atomically move one component ``prepared → requested`` before any network call.

    Returns ``None`` when another request already claimed or resolved the component. The caller
    owns the transaction and must commit before calling the transport.
    """
    component = components(session, event.id).get(kind)
    if component is None:
        return None
    result = session.execute(
        update(NotificationComponent)
        .where(
            NotificationComponent.id == component.id,
            NotificationComponent.status == "prepared",
        )
        .values(status="requested", error_code=None, updated_at=utc_now_iso())
        .execution_options(synchronize_session="fetch")
    )
    if result.rowcount != 1:
        return None
    attempt = create_attempt(session, event=event, kind=kind, status="requested")
    refresh_event_status(session, event)
    return attempt


def refresh_event_status(session: Session, event: NotificationEvent) -> str:
    values = components(session, event.id)
    statuses = {kind: values[kind].status for kind in COMPONENT_KINDS}
    accepted = [kind for kind, status in statuses.items() if status == "accepted"]
    uncertain = [kind for kind, status in statuses.items() if status == "uncertain"]
    failed = [kind for kind, status in statuses.items() if status == "failed"]
    skipped = [kind for kind, status in statuses.items() if status == "skipped"]
    if len(accepted) == 2:
        event.status = "accepted"
    elif accepted and (failed or uncertain or skipped):
        event.status = "partial"
    elif uncertain:
        event.status = "uncertain"
    elif failed and not accepted:
        event.status = "failed"
    elif skipped and not accepted:
        event.status = "skipped"
    elif all(status == "requested" for status in statuses.values()):
        event.status = "sending"
    elif all(status == "queued" for status in statuses.values()):
        event.status = "queued"
    event.updated_at = utc_now_iso()
    session.flush()
    return event.status


def set_component(
    session: Session,
    *,
    event: NotificationEvent,
    kind: str,
    status: str,
    provider_message_id: str | None = None,
    error_code: str | None = None,
) -> NotificationComponent:
    if kind not in COMPONENT_KINDS or status not in COMPONENT_STATUSES:
        raise NotificationError("invalid_component", "Componente o estado inválido.")
    component = components(session, event.id)[kind]
    if component.status == "accepted" and status != "accepted":
        raise NotificationError("accepted_component", "Un componente aceptado no se reenvía.")
    if component.status == "uncertain" and status != "uncertain":
        raise NotificationError(
            "uncertain_requires_review",
            "Un componente incierto exige conciliación explícita; no se reenvía.",
        )
    component.status = status
    if provider_message_id:
        component.provider_message_id = provider_message_id
    if error_code:
        component.error_code = error_code
    component.updated_at = utc_now_iso()
    session.flush()
    refresh_event_status(session, event)
    return component


def create_attempt(
    session: Session,
    *,
    event: NotificationEvent,
    kind: str,
    status: str = "requested",
    http_status: int | None = None,
    error_code: str | None = None,
    provider_message_id: str | None = None,
    duration_ms: int | None = None,
    evidence_note: str | None = None,
) -> NotificationAttempt:
    component = components(session, event.id)[kind]
    attempt_no = component.attempt_count + 1
    attempt = NotificationAttempt(
        event_id=event.id,
        component_kind=kind,
        attempt_no=attempt_no,
        status=status,
        requested_at=utc_now_iso(),
        http_status=http_status,
        error_code=error_code,
        provider_message_id=provider_message_id,
        duration_ms=duration_ms,
        evidence_note=evidence_note,
    )
    session.add(attempt)
    component.attempt_count = attempt_no
    session.flush()
    return attempt


def finish_attempt(
    session: Session,
    attempt: NotificationAttempt,
    *,
    status: str,
    http_status: int | None = None,
    error_code: str | None = None,
    provider_message_id: str | None = None,
    duration_ms: int | None = None,
    evidence_note: str | None = None,
) -> None:
    attempt.status = status
    attempt.finished_at = utc_now_iso()
    attempt.http_status = http_status
    attempt.error_code = error_code
    attempt.provider_message_id = provider_message_id
    attempt.duration_ms = duration_ms
    attempt.evidence_note = evidence_note
    session.flush()


def list_events(session: Session, case_id: str) -> list[NotificationEvent]:
    return list(
        session.scalars(
            select(NotificationEvent)
            .where(NotificationEvent.case_id == case_id)
            .order_by(NotificationEvent.created_at.desc())
        )
    )


def get_event(session: Session, case_id: str, event_id: str) -> NotificationEvent:
    event = session.scalar(
        select(NotificationEvent).where(
            NotificationEvent.id == event_id, NotificationEvent.case_id == case_id
        )
    )
    if event is None:
        raise NotificationError("event_not_found", "El evento no existe en este caso.")
    return event


def event_view(session: Session, event: NotificationEvent) -> dict[str, Any]:
    contact = session.get(ContactChannel, event.contact_id)
    values = components(session, event.id)
    statuses = {kind: values[kind].status for kind in COMPONENT_KINDS}
    retryable = event.status in {"failed", "partial"} and not any(
        status in {"uncertain", "requested"} for status in statuses.values()
    )
    return {
        "id": event.id,
        "mode": event.mode,
        "mode_label": MODE_LABELS.get(event.mode, event.mode),
        "status": event.status,
        "status_label": EVENT_LABELS.get(event.status, event.status),
        "created_at": event.created_at,
        "contact_alias": contact.alias if contact else "Contacto eliminado",
        "masked_chat": mask_chat_id(contact.chat_id) if contact else "••••",
        "version_id": event.report_version_id,
        "manifest_sha256": event.manifest_sha256,
        "retryable": retryable,
        "components": {
            kind: {
                "status": values[kind].status,
                "status_label": COMPONENT_LABELS.get(values[kind].status, values[kind].status),
                "provider_message_id": values[kind].provider_message_id,
                "error_code": values[kind].error_code,
                "error_label": ERROR_LABELS.get(values[kind].error_code or "", ""),
                "attempt_count": values[kind].attempt_count,
            }
            for kind in COMPONENT_KINDS
        },
    }
