"""Short-transaction manual delivery executor."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from secguard_advisor.config import Settings
from secguard_advisor.db.models import (
    ContactChannel,
    NotificationAttempt,
    NotificationComponent,
    NotificationEvent,
    ReportArtifact,
    ReportConfirmation,
    ReportVersion,
    utc_now_iso,
)
from secguard_advisor.notifications.channels.base import TelegramError, TelegramTransport
from secguard_advisor.notifications.contacts import eligibility_error
from secguard_advisor.notifications.delivery import (
    claim_component,
    components,
    finish_attempt,
    refresh_event_status,
)
from secguard_advisor.notifications.errors import NotificationError
from secguard_advisor.notifications.manifest import build_manifest, build_recipient_manifest
from secguard_advisor.reports.canonical import parse_json

SENDABLE = ("prepared",)
BLOCKABLE = ("prepared", "failed")
RESOLVED = ("accepted", "uncertain", "requested")


class _Revalidation:
    __slots__ = ("contact", "error_code", "version")

    def __init__(
        self,
        contact: ContactChannel | None = None,
        version: ReportVersion | None = None,
        error_code: str | None = None,
    ) -> None:
        self.contact = contact
        self.version = version
        self.error_code = error_code

    @property
    def ok(self) -> bool:
        return self.error_code is None and self.contact is not None and self.version is not None


def _revalidate(session: Session, event: NotificationEvent) -> _Revalidation:
    """Revalidate the confirmed set, the recipient and this event's own scope."""
    contact = session.get(ContactChannel, event.contact_id)
    version = session.get(ReportVersion, event.report_version_id)
    if contact is None or version is None or version.status != "ready":
        return _Revalidation(error_code="component_revalidation_failed")
    stored = parse_json(event.manifest_json)
    approved_recipients_sha256 = stored.get("approved_recipients_sha256")
    if event.mode == "manual":
        if not event.confirmation_id:
            return _Revalidation(error_code="manifest_mismatch")
        confirmation = session.get(ReportConfirmation, event.confirmation_id)
        if confirmation is None or confirmation.invalidated_at is not None:
            return _Revalidation(error_code="manifest_mismatch")
        approved_ids = list(parse_json(confirmation.contacts_json))
        if contact.id not in approved_ids:
            return _Revalidation(error_code="manifest_mismatch")
        current = build_manifest(session, version, approved_ids)
        if current["manifest_sha256"] != confirmation.manifest_sha256:
            confirmation.invalidated_at = utc_now_iso()
            session.flush()
            return _Revalidation(error_code="manifest_mismatch")
        if approved_recipients_sha256 != current["recipients_sha256"]:
            return _Revalidation(error_code="manifest_mismatch")
    reason = eligibility_error(session, contact=contact, case_id=event.case_id)
    if reason is not None:
        return _Revalidation(error_code=reason)
    if approved_recipients_sha256 is None:
        return _Revalidation(error_code="manifest_mismatch")
    expected = build_recipient_manifest(
        session,
        version,
        contact.id,
        approved_recipients_sha256=approved_recipients_sha256,
    )
    if expected["manifest_sha256"] != event.manifest_sha256:
        return _Revalidation(error_code="manifest_mismatch")
    return _Revalidation(contact=contact, version=version)


def _artifact_path(session: Session, version: ReportVersion) -> Path | None:
    artifact = session.scalar(
        select(ReportArtifact).where(
            ReportArtifact.report_version_id == version.id,
            ReportArtifact.kind == "pdf",
        )
    )
    return Path(artifact.relative_path) if artifact is not None else None


def load_validated_pdf(
    settings: Settings, session: Session, version: ReportVersion, expected_sha256: str
) -> tuple[bytes | None, str | None]:
    """Read the PDF once and verify the exact bytes against the approved hash."""
    relative = _artifact_path(session, version)
    if relative is None:
        return None, "document_render_failed"
    path = settings.reports_dir / relative
    if not path.is_file():
        return None, "document_render_failed"
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        return None, "pdf_integrity_mismatch"
    return data, None


def _block_pending(session: Session, event: NotificationEvent, *, error_code: str) -> None:
    for component in components(session, event.id).values():
        if component.status in BLOCKABLE:
            component.status = "failed"
            component.error_code = error_code
            component.updated_at = utc_now_iso()
    refresh_event_status(session, event)


def _skip_remaining(session: Session, event: NotificationEvent, *, error_code: str) -> None:
    for component in components(session, event.id).values():
        if component.status in BLOCKABLE:
            component.status = "skipped"
            component.error_code = error_code
            component.updated_at = utc_now_iso()
    refresh_event_status(session, event)


def _finish(
    session: Session,
    *,
    event: NotificationEvent,
    kind: str,
    attempt_id: str,
    status: str,
    provider_message_id: str | None = None,
    error_code: str | None = None,
    duration_ms: int | None = None,
) -> bool:
    """Resolve a claimed component exactly once; stale results never overwrite newer state."""
    component = components(session, event.id)[kind]
    if component.status != "requested":
        return False
    attempt = session.get(NotificationAttempt, attempt_id)
    if attempt is None:
        return False
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
    component.status = status
    component.provider_message_id = provider_message_id or component.provider_message_id
    component.error_code = error_code
    component.updated_at = utc_now_iso()
    refresh_event_status(session, event)
    return True


def _status_snapshot(factory: sessionmaker[Session], event_id: str) -> tuple[str, dict[str, str]]:
    with factory() as session:
        event = session.get(NotificationEvent, event_id)
        assert event is not None
        return event.status, {
            kind: row.status for kind, row in components(session, event.id).items()
        }


def execute_event(
    factory: sessionmaker[Session],
    settings: Settings,
    transport: TelegramTransport,
    event_id: str,
) -> str:
    """Execute summary then PDF with short transactions and per-component claims."""
    with factory() as session:
        event = session.get(NotificationEvent, event_id)
        if event is None:
            raise NotificationError("event_not_found", "El evento no existe.")
        if event.status in {"accepted", "skipped"}:
            return event.status
        manifest = parse_json(event.manifest_json)
        version = session.get(ReportVersion, event.report_version_id)
        assert version is not None
        statuses = {kind: row.status for kind, row in components(session, event.id).items()}
        event.status = "sending"
        session.commit()

    if statuses.get("document") in SENDABLE:
        with factory() as read_session:
            pdf_bytes, pdf_error = load_validated_pdf(
                settings, read_session, version, manifest["pdf_sha256"]
            )
        if pdf_error is not None:
            with factory() as session:
                event = session.get(NotificationEvent, event_id)
                assert event is not None
                _block_pending(session, event, error_code=pdf_error)
                session.commit()
                return event.status
    else:
        pdf_bytes = None

    for kind in ("summary", "document"):
        with factory() as session:
            event = session.get(NotificationEvent, event_id)
            assert event is not None
            if components(session, event.id)[kind].status == "accepted":
                continue
            checked = _revalidate(session, event)
            if not checked.ok:
                _skip_remaining(
                    session, event, error_code=checked.error_code or "manifest_mismatch"
                )
                session.commit()
                return event.status
            attempt = claim_component(session, event=event, kind=kind)
            if attempt is None:
                session.commit()
                status, current = _status_snapshot(factory, event_id)
                if current.get(kind) == "accepted":
                    continue
                return status
            attempt_id = attempt.id
            chat_id = checked.contact.chat_id
            filename = f"informe-v{checked.version.version_number}.pdf"
            caption = f"Informe ejecutivo v{checked.version.version_number}"
            session.commit()

        started = time.perf_counter()
        try:
            if kind == "summary":
                result = transport.send_message(chat_id, manifest["outbound_text"])
            else:
                if pdf_bytes is None:
                    raise TelegramError("document_render_failed", "PDF no disponible.")
                if hashlib.sha256(pdf_bytes).hexdigest() != manifest["pdf_sha256"]:
                    raise TelegramError("pdf_integrity_mismatch", "El PDF no coincide.")
                result = transport.send_document(chat_id, filename, pdf_bytes, caption)
        except TelegramError as exc:
            status = "uncertain" if exc.uncertain else "failed"
            with factory() as session:
                event = session.get(NotificationEvent, event_id)
                assert event is not None
                _finish(
                    session,
                    event=event,
                    kind=kind,
                    attempt_id=attempt_id,
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
            assert event is not None
            _finish(
                session,
                event=event,
                kind=kind,
                attempt_id=attempt_id,
                status="accepted",
                provider_message_id=result.message_id,
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
            session.commit()

    with factory() as session:
        event = session.get(NotificationEvent, event_id)
        assert event is not None
        return event.status


def retry_event(
    factory: sessionmaker[Session], settings: Settings, transport: TelegramTransport, event_id: str
) -> str:
    """Requeue definitive failures only; uncertain and in-flight results need explicit review."""
    with factory() as session:
        event = session.get(NotificationEvent, event_id)
        if event is None:
            raise NotificationError("event_not_found", "El evento no existe.")
        values = components(session, event.id)
        if any(row.status in {"uncertain", "requested"} for row in values.values()):
            raise NotificationError(
                "uncertain_requires_review",
                "Hay un componente incierto o en vuelo; exige revisión explícita.",
            )
        if event.status not in {"failed", "partial"}:
            raise NotificationError("retry_not_allowed", "El evento no admite reintento manual.")
        retryable = [
            row
            for row in values.values()
            if row.status == "failed"
            or (row.status == "skipped" and row.error_code == "summary_failed")
        ]
        if not retryable:
            raise NotificationError("retry_not_allowed", "No hay componentes reintentables.")
        for component in retryable:
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
