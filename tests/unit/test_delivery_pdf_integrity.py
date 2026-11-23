"""PDF integrity against the confirmed manifest."""

from __future__ import annotations

import hashlib
from pathlib import Path

from sqlalchemy import select
from tests.fixtures.notifications import (
    create_ready_report,
    make_confirmation,
    make_eligible_contact,
    make_prepared_event,
)

from secguard_advisor.db.models import ReportArtifact
from secguard_advisor.notifications.channels.telegram import StubTelegramTransport
from secguard_advisor.notifications.delivery import components
from secguard_advisor.notifications.executor import execute_event, retry_event
from secguard_advisor.reports.canonical import parse_json


def _pdf_path(report_context, version_id: str) -> Path:
    with report_context.session_factory() as session:
        artifact = session.scalar(
            select(ReportArtifact).where(
                ReportArtifact.report_version_id == version_id,
                ReportArtifact.kind == "pdf",
            )
        )
        return report_context.settings.reports_dir / artifact.relative_path


def test_tampered_pdf_blocks_before_any_message(report_context) -> None:
    report = create_ready_report(report_context)
    contact, _ = make_eligible_contact(report_context)
    confirmation = make_confirmation(report_context, report, [contact.id])
    event_id, manifest = make_prepared_event(report_context, contact, confirmation)
    path = _pdf_path(report_context, report.version_id)
    original = path.read_bytes()
    path.write_bytes(original + b"tampered")

    transport = StubTelegramTransport()
    status = execute_event(
        report_context.session_factory, report_context.settings, transport, event_id
    )

    assert status == "failed"
    assert transport.calls == []
    with report_context.session_factory() as session:
        values = components(session, event_id)
        assert values["summary"].status == "failed"
        assert values["document"].status == "failed"
        assert values["summary"].error_code == "pdf_integrity_mismatch"
        assert values["document"].error_code == "pdf_integrity_mismatch"

    path.write_bytes(original)
    status = retry_event(
        report_context.session_factory, report_context.settings, transport, event_id
    )
    assert status == "accepted"
    document = next(call for call in transport.calls if call.method == "send_document")
    assert hashlib.sha256(document.content).hexdigest() == manifest["pdf_sha256"]


class MutatingTransport(StubTelegramTransport):
    """Changes the file on disk while the summary is being accepted."""

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path

    def send_message(self, chat_id: str, text: str):
        result = super().send_message(chat_id, text)
        self.path.write_bytes(self.path.read_bytes() + b"changed-after-preflight")
        return result


def test_document_sends_the_validated_bytes_not_a_second_read(report_context) -> None:
    report = create_ready_report(report_context)
    contact, _ = make_eligible_contact(report_context)
    confirmation = make_confirmation(report_context, report, [contact.id])
    event_id, manifest = make_prepared_event(report_context, contact, confirmation)
    path = _pdf_path(report_context, report.version_id)
    transport = MutatingTransport(path)

    status = execute_event(
        report_context.session_factory, report_context.settings, transport, event_id
    )

    assert status == "accepted"
    documents = [call for call in transport.calls if call.method == "send_document"]
    assert len(documents) == 1
    assert hashlib.sha256(documents[0].content).hexdigest() == manifest["pdf_sha256"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() != manifest["pdf_sha256"]


def test_missing_pdf_blocks_with_document_error(report_context) -> None:
    report = create_ready_report(report_context)
    contact, _ = make_eligible_contact(report_context)
    confirmation = make_confirmation(report_context, report, [contact.id])
    event_id, _manifest = make_prepared_event(report_context, contact, confirmation)
    path = _pdf_path(report_context, report.version_id)
    path.unlink()
    transport = StubTelegramTransport()

    status = execute_event(
        report_context.session_factory, report_context.settings, transport, event_id
    )

    assert status == "failed"
    assert transport.calls == []
    with report_context.session_factory() as session:
        assert components(session, event_id)["document"].error_code == "document_render_failed"


def test_confirmed_pdf_hash_is_not_updated_automatically(report_context) -> None:
    report = create_ready_report(report_context)
    contact, _ = make_eligible_contact(report_context)
    confirmation = make_confirmation(report_context, report, [contact.id])
    event_id, manifest = make_prepared_event(report_context, contact, confirmation)
    path = _pdf_path(report_context, report.version_id)
    path.write_bytes(b"%PDF-1.4\n% different file\n%%EOF\n")
    transport = StubTelegramTransport()

    execute_event(report_context.session_factory, report_context.settings, transport, event_id)

    with report_context.session_factory() as session:
        from secguard_advisor.db.models import NotificationEvent

        event = session.get(NotificationEvent, event_id)
        stored = parse_json(event.manifest_json)
    assert stored["pdf_sha256"] == manifest["pdf_sha256"]
    assert stored["manifest_sha256"] == manifest["manifest_sha256"]
