"""Short-transaction manual delivery executor."""

from __future__ import annotations

import time

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from secguard_advisor.config import Settings
from secguard_advisor.db.models import (
    ContactChannel,
    NotificationAttempt,
    NotificationComponent,
    NotificationEvent,
    ReportArtifact,
    ReportVersion,
    utc_now_iso,
)
from secguard_advisor.notifications.channels.base import TelegramError, TelegramTransport
from secguard_advisor.notifications.contacts import is_eligible
from secguard_advisor.notifications.delivery import (
    components,
    create_attempt,
    finish_attempt,
    refresh_event_status,
)
from secguard_advisor.notifications.errors import NotificationError
from secguard_advisor.notifications.manifest import build_manifest
from secguard_advisor.reports.canonical import parse_json


def _revalidate(
    session: Session, event: NotificationEvent
) -> tuple[ContactChannel, ReportVersion] | None:
    contact = session.get(ContactChannel, event.contact_id)
    version = session.get(ReportVersion, event.report_version_id)
    if contact is None or version is None or version.status != "ready":
        return None
    if not is_eligible(session, contact=contact, case_id=event.case_id):
        return None
    recipients = [contact.id]
    manifest = build_manifest(session, version, recipients)
    if manifest["manifest_sha256"] != event.manifest_sha256:
        return None
    return contact, version


def _pdf_bytes(session: Session, settings: Settings, version: ReportVersion) -> bytes | None:
    artifact = session.scalar(
        select(ReportArtifact).where(
            ReportArtifact.report_version_id == version.id,
            ReportArtifact.kind == "pdf",
        )
    )
    if artifact is None:
        return None
    path = settings.reports_dir / artifact.relative_path
    return path.read_bytes() if path.exists() else None


def _record(
    session: Session,
    *,
    event: NotificationEvent,
    kind: str,
    attempt: NotificationAttempt,
    status: str,
    provider_message_id: str | None = None,
    error_code: str | None = None,
    duration_ms: int | None = None,
) -> None:
    finish_attempt(
        session,
        attempt,
        status=status,
        http_status=None,
        error_code=error_code,
        provider_message_id=provider_message_id,
        duration_ms=duration_ms,
        evidence_note=None,
    )
    component = components(session, event.id)[kind]
    component.provider_message_id = provider_message_id or component.provider_message_id
    component.error_code = error_code
    component.status = status
    component.updated_at = utc_now_iso()
    refresh_event_status(session, event)


def _skip_remaining(session: Session, event: NotificationEvent, *, error_code: str) -> None:
    for _kind, component in components(session, event.id).items():
        if component.status != "accepted":
            component.status = "skipped"
            component.error_code = error_code
            component.updated_at = utc_now_iso()
    refresh_event_status(session, event)


def execute_event(
    factory: sessionmaker[Session],
    settings: Settings,
    transport: TelegramTransport,
    event_id: str,
) -> str:
    """Execute summary then PDF with short transactions and per-component checks."""
    with factory() as session:
        event = session.get(NotificationEvent, event_id)
        if event is None:
            raise NotificationError("event_not_found", "El evento no existe.")
        event.status = "sending"
        session.commit()
        manifest = parse_json(event.manifest_json)

    for kind in ("summary", "document"):
        with factory() as session:
            event = session.get(NotificationEvent, event_id)
            component = components(session, event.id)[kind]
            if component.status == "accepted":
                continue
            checked = _revalidate(session, event)
            if checked is None:
                _skip_remaining(session, event, error_code="component_revalidation_failed")
                session.commit()
                return event.status
            contact, version = checked
            component.status = "requested"
            component.error_code = None
            attempt = create_attempt(session, event=event, kind=kind, status="requested")
            session.commit()
            chat_id = contact.chat_id
            if kind == "document":
                pdf = _pdf_bytes(session, settings, version)
                if pdf is None:
                    _record(
                        session,
                        event=event,
                        kind=kind,
                        attempt=attempt,
                        status="failed",
                        error_code="document_render_failed",
                    )
                    _skip_remaining(session, event, error_code="document_render_failed")
                    session.commit()
                    return event.status
            session.commit()

        started = time.perf_counter()
        try:
            if kind == "summary":
                result = transport.send_message(chat_id, manifest["outbound_text"])
            else:
                with factory() as session:
                    event = session.get(NotificationEvent, event_id)
                    version = session.get(ReportVersion, event.report_version_id)
                    pdf = _pdf_bytes(session, settings, version)
                if pdf is None:
                    raise TelegramError("document_render_failed", "PDF no disponible.")
                result = transport.send_document(
                    chat_id,
                    f"informe-v{version.version_number}.pdf",
                    pdf,
                    f"Informe ejecutivo v{version.version_number}",
                )
        except TelegramError as exc:
            with factory() as session:
                event = session.get(NotificationEvent, event_id)
                attempt = session.scalar(
                    select(NotificationAttempt).where(
                        NotificationAttempt.event_id == event.id,
                        NotificationAttempt.component_kind == kind,
                        NotificationAttempt.attempt_no
                        == components(session, event.id)[kind].attempt_count,
                    )
                )
                status = "uncertain" if exc.uncertain else "failed"
                _record(
                    session,
                    event=event,
                    kind=kind,
                    attempt=attempt,
                    status=status,
                    error_code=exc.code,
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
                if kind == "summary" and status == "failed":
                    _skip_remaining(session, event, error_code="summary_failed")
                session.commit()
                return event.status
        with factory() as session:
            event = session.get(NotificationEvent, event_id)
            attempt = session.scalar(
                select(NotificationAttempt).where(
                    NotificationAttempt.event_id == event.id,
                    NotificationAttempt.component_kind == kind,
                    NotificationAttempt.attempt_no
                    == components(session, event.id)[kind].attempt_count,
                )
            )
            _record(
                session,
                event=event,
                kind=kind,
                attempt=attempt,
                status="accepted",
                provider_message_id=result.message_id,
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
            session.commit()
    with factory() as session:
        event = session.get(NotificationEvent, event_id)
        return event.status


def retry_event(
    factory: sessionmaker[Session], settings: Settings, transport: TelegramTransport, event_id: str
) -> str:
    with factory() as session:
        event = session.get(NotificationEvent, event_id)
        if event is None:
            raise NotificationError("event_not_found", "El evento no existe.")
        if event.status not in {"failed", "partial"}:
            raise NotificationError("retry_not_allowed", "El evento no admite reintento manual.")
        for component in components(session, event.id).values():
            if component.status != "accepted":
                component.status = "prepared"
                component.error_code = None
                component.updated_at = utc_now_iso()
        event.status = "queued"
        session.commit()
    return execute_event(factory, settings, transport, event_id)


def recover_interrupted(factory: sessionmaker[Session]) -> int:
    """Mark in-flight requests as uncertain; never resend automatically."""
    with factory() as session:
        rows = list(
            session.scalars(
                select(NotificationComponent).where(NotificationComponent.status == "requested")
            )
        )
        for component in rows:
            component.status = "uncertain"
            component.error_code = "interrupted"
            component.updated_at = utc_now_iso()
            event = session.get(NotificationEvent, component.event_id)
            if event is not None:
                refresh_event_status(session, event)
        attempts = list(
            session.scalars(
                select(NotificationAttempt).where(NotificationAttempt.status == "requested")
            )
        )
        for attempt in attempts:
            attempt.status = "uncertain"
            attempt.finished_at = utc_now_iso()
            attempt.error_code = "interrupted"
        session.commit()
        return len(rows)
