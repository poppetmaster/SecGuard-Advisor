"""Manual send, reuse and manifest mismatch."""

from __future__ import annotations

import pytest
from tests.fixtures.notifications import create_ready_report, make_eligible_contact

from secguard_advisor.db.models import NotificationEvent
from secguard_advisor.notifications.channels.telegram import StubTelegramTransport
from secguard_advisor.notifications.confirmations import create_confirmation
from secguard_advisor.notifications.errors import NotificationError
from secguard_advisor.notifications.manual import send_manual


def test_manual_send_is_idempotent_and_does_not_regenerate(report_context) -> None:
    result = create_ready_report(report_context)
    contact, _verify_transport = make_eligible_contact(report_context)
    transport = StubTelegramTransport()
    with report_context.session_factory() as session:
        confirmation = create_confirmation(
            session,
            case_id=report_context.case_id,
            report_id=result.report_id,
            version_number=result.version_number,
            contact_ids=[contact.id],
            created_by="Tester",
        )
        session.commit()
        confirmation_id = confirmation.id
    events = send_manual(
        report_context.session_factory,
        report_context.settings,
        transport,
        case_id=report_context.case_id,
        confirmation_id=confirmation_id,
    )
    assert len(events) == 1
    assert len(transport.calls) == 2
    send_manual(
        report_context.session_factory,
        report_context.settings,
        transport,
        case_id=report_context.case_id,
        confirmation_id=confirmation_id,
    )
    assert len(transport.calls) == 2
    with report_context.session_factory() as session:
        assert session.query(NotificationEvent).count() == 1


def test_manifest_mismatch_blocks_send(report_context) -> None:
    result = create_ready_report(report_context)
    contact, _verify_transport = make_eligible_contact(report_context)
    transport = StubTelegramTransport()
    with report_context.session_factory() as session:
        confirmation = create_confirmation(
            session,
            case_id=report_context.case_id,
            report_id=result.report_id,
            version_number=result.version_number,
            contact_ids=[contact.id],
            created_by="Tester",
        )
        session.commit()
        confirmation_id = confirmation.id
        persisted = session.get(type(contact), contact.id)
        persisted.alias = "Cambiado"
        session.commit()
    with pytest.raises(NotificationError) as error:
        send_manual(
            report_context.session_factory,
            report_context.settings,
            transport,
            case_id=report_context.case_id,
            confirmation_id=confirmation_id,
        )
    assert error.value.code == "manifest_mismatch"
    assert transport.calls == []
