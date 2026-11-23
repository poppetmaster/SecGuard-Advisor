"""Timeout, partial delivery, restart and revocation between components."""

from __future__ import annotations

from tests.fixtures.notifications import create_ready_report, make_eligible_contact

from secguard_advisor.db.models import NotificationComponent, ReportVersion
from secguard_advisor.notifications.channels.telegram import StubTelegramTransport
from secguard_advisor.notifications.confirmations import create_confirmation
from secguard_advisor.notifications.contacts import set_consent
from secguard_advisor.notifications.delivery import components, ensure_event
from secguard_advisor.notifications.executor import execute_event, recover_interrupted, retry_event
from secguard_advisor.reports.canonical import parse_json


def _event(report_context, transport: StubTelegramTransport | None = None):
    result = create_ready_report(report_context)
    contact, _verify_transport = make_eligible_contact(report_context)
    transport = transport or StubTelegramTransport()
    with report_context.session_factory() as session:
        confirmation = create_confirmation(
            session,
            case_id=report_context.case_id,
            report_id=result.report_id,
            version_number=result.version_number,
            contact_ids=[contact.id],
            created_by="Prueba",
        )
        manifest = parse_json(confirmation.manifest_json)
        event, _ = ensure_event(
            session,
            version=session.get(ReportVersion, result.version_id),
            contact=contact,
            manifest=manifest,
            mode="manual",
            confirmation_id=confirmation.id,
        )
        session.commit()
        return event.id, contact.id, transport


def test_timeout_is_uncertain_and_not_retried_automatically(report_context) -> None:
    event_id, _, transport = _event(report_context)
    transport.uncertain_on.add("send_message")
    status = execute_event(
        report_context.session_factory, report_context.settings, transport, event_id
    )
    assert status == "uncertain"
    with report_context.session_factory() as session:
        values = components(session, event_id)
        assert values["summary"].status == "uncertain"
        assert values["document"].status == "prepared"


def test_partial_delivery_retries_only_the_pdf(report_context) -> None:
    event_id, _, transport = _event(report_context)
    transport.fail_on.add("send_document")
    status = execute_event(
        report_context.session_factory, report_context.settings, transport, event_id
    )
    assert status == "partial"
    transport.fail_on.discard("send_document")
    status = retry_event(
        report_context.session_factory, report_context.settings, transport, event_id
    )
    assert status == "accepted"
    assert sum(1 for call in transport.calls if call.method == "send_message") == 1
    assert sum(1 for call in transport.calls if call.method == "send_document") == 2


class RevokingTransport(StubTelegramTransport):
    def __init__(self, factory, contact_id: str):
        super().__init__()
        self.factory = factory
        self.contact_id = contact_id

    def send_message(self, chat_id: str, text: str):
        result = super().send_message(chat_id, text)
        with self.factory() as session:
            set_consent(session, self.contact_id, "revoked", declared_by="Prueba")
            session.commit()
        return result


def test_revocation_between_components_keeps_accepted_summary(report_context) -> None:
    event_id, contact_id, _ = _event(report_context)
    transport = RevokingTransport(report_context.session_factory, contact_id)
    status = execute_event(
        report_context.session_factory, report_context.settings, transport, event_id
    )
    assert status == "partial"
    with report_context.session_factory() as session:
        values = components(session, event_id)
        assert values["summary"].status == "accepted"
        assert values["document"].status == "skipped"
        assert values["document"].error_code == "consent_missing"


def test_restart_marks_in_flight_as_uncertain(report_context) -> None:
    event_id, _, _ = _event(report_context)
    with report_context.session_factory() as session:
        components(session, event_id)["summary"].status = "requested"
        session.commit()
    changed = recover_interrupted(report_context.session_factory)
    assert changed == 1
    with report_context.session_factory() as session:
        values = components(session, event_id)
        assert values["summary"].status == "uncertain"
        assert values["summary"].error_code == "interrupted"
        assert session.get(NotificationComponent, values["summary"].id) is not None
