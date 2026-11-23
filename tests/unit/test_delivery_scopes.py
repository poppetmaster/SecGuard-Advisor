"""Manifest scope: approved set versus per-recipient events."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from tests.fixtures.notifications import (
    create_ready_report,
    make_confirmation,
    make_eligible_contact,
    make_prepared_event,
)

from secguard_advisor.db.models import NotificationEvent, ReportConfirmation
from secguard_advisor.notifications.channels.telegram import StubTelegramTransport
from secguard_advisor.notifications.contacts import set_consent
from secguard_advisor.notifications.delivery import components
from secguard_advisor.notifications.manual import send_manual
from secguard_advisor.reports.canonical import parse_json


def test_two_recipients_receive_summary_and_pdf_each(report_context) -> None:
    report = create_ready_report(report_context)
    first, _ = make_eligible_contact(report_context, alias="Operaciones", chat_id="111111111")
    second, _ = make_eligible_contact(report_context, alias="Dirección", chat_id="222222222")
    confirmation = make_confirmation(report_context, report, [first.id, second.id])
    transport = StubTelegramTransport()

    events = send_manual(
        report_context.session_factory,
        report_context.settings,
        transport,
        case_id=report_context.case_id,
        confirmation_id=confirmation.id,
    )

    assert len(events) == 2
    messages = [call for call in transport.calls if call.method == "send_message"]
    documents = [call for call in transport.calls if call.method == "send_document"]
    assert len(messages) == 2
    assert len(documents) == 2
    assert {call.chat_id for call in messages} == {"111111111", "222222222"}
    assert {call.chat_id for call in documents} == {"111111111", "222222222"}
    with report_context.session_factory() as session:
        rows = list(session.scalars(select(NotificationEvent)))
        assert {row.status for row in rows} == {"accepted"}
        for row in rows:
            values = components(session, row.id)
            assert values["summary"].status == "accepted"
            assert values["document"].status == "accepted"


def test_event_manifest_is_recipient_scoped_not_the_confirmed_set(report_context) -> None:
    report = create_ready_report(report_context)
    first, _ = make_eligible_contact(report_context, alias="Operaciones", chat_id="111111111")
    second, _ = make_eligible_contact(report_context, alias="Dirección", chat_id="222222222")
    confirmation = make_confirmation(report_context, report, [first.id, second.id])
    _event_id, event_manifest = make_prepared_event(report_context, first, confirmation)

    with report_context.session_factory() as session:
        stored = session.get(ReportConfirmation, confirmation.id)
        set_manifest = parse_json(stored.manifest_json)

    assert len(set_manifest["recipients"]) == 2
    assert len(event_manifest["recipients"]) == 1
    assert event_manifest["recipients"][0]["contact_id"] == first.id
    assert event_manifest["approved_recipients_sha256"] == set_manifest["recipients_sha256"]
    assert event_manifest["pdf_sha256"] == set_manifest["pdf_sha256"]
    assert event_manifest["outbound_text_sha256"] == set_manifest["outbound_text_sha256"]
    assert event_manifest["manifest_sha256"] != set_manifest["manifest_sha256"]


def test_revoked_recipient_does_not_block_the_other(report_context) -> None:
    report = create_ready_report(report_context)
    revoked, _ = make_eligible_contact(report_context, alias="Revocado", chat_id="111111111")
    allowed, _ = make_eligible_contact(report_context, alias="Permitido", chat_id="222222222")
    confirmation = make_confirmation(report_context, report, [revoked.id, allowed.id])
    with report_context.session_factory() as session:
        set_consent(session, revoked.id, "revoked", declared_by="Prueba")
        session.commit()
    transport = StubTelegramTransport()

    send_manual(
        report_context.session_factory,
        report_context.settings,
        transport,
        case_id=report_context.case_id,
        confirmation_id=confirmation.id,
    )

    assert {call.chat_id for call in transport.calls if call.chat_id} == {"222222222"}
    with report_context.session_factory() as session:
        blocked = session.scalar(
            select(NotificationEvent).where(NotificationEvent.contact_id == revoked.id)
        )
        delivered = session.scalar(
            select(NotificationEvent).where(NotificationEvent.contact_id == allowed.id)
        )
        assert blocked.status == "skipped"
        blocked_values = components(session, blocked.id)
        assert blocked_values["summary"].status == "skipped"
        assert blocked_values["document"].status == "skipped"
        assert blocked_values["summary"].error_code == "consent_missing"
        assert delivered.status == "accepted"


def test_changed_alias_invalidates_the_confirmation_and_blocks_everyone(report_context) -> None:
    report = create_ready_report(report_context)
    first, _ = make_eligible_contact(report_context, alias="Operaciones", chat_id="111111111")
    second, _ = make_eligible_contact(report_context, alias="Dirección", chat_id="222222222")
    confirmation = make_confirmation(report_context, report, [first.id, second.id])
    with report_context.session_factory() as session:
        from secguard_advisor.db.models import ContactChannel

        session.get(ContactChannel, first.id).alias = "Otro alias"
        session.commit()
    transport = StubTelegramTransport()

    with pytest.raises(Exception) as error:
        send_manual(
            report_context.session_factory,
            report_context.settings,
            transport,
            case_id=report_context.case_id,
            confirmation_id=confirmation.id,
        )
    assert getattr(error.value, "code", "") == "manifest_mismatch"
    assert transport.calls == []
