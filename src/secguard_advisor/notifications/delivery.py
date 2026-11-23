"""Notification events, components, attempts and idempotency."""

from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy import select
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
    rule_id: str | None = None,
    rule_version: int | None = None,
) -> tuple[NotificationEvent, bool]:
    key = idempotency_key(version.case_id, version.id, contact.id)
    existing = session.scalar(
        select(NotificationEvent).where(NotificationEvent.idempotency_key == key)
    )
    if existing is not None:
        return existing, False
    event = NotificationEvent(
        case_id=version.case_id,
        report_version_id=version.id,
        contact_id=contact.id,
        mode=mode,
        rule_id=rule_id,
        rule_version=rule_version,
        idempotency_key=key,
        manifest_json=canonical_json(manifest),
        manifest_sha256=manifest["manifest_sha256"],
        content_policy_json=canonical_json(manifest["content_policy"]),
        content_sha256=content_hash(manifest),
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
        "components": {
            kind: {
                "status": values[kind].status,
                "status_label": COMPONENT_LABELS.get(values[kind].status, values[kind].status),
                "provider_message_id": values[kind].provider_message_id,
                "error_code": values[kind].error_code,
                "attempt_count": values[kind].attempt_count,
            }
            for kind in COMPONENT_KINDS
        },
    }
