"""Confirmation lifecycle and invalidation."""

from __future__ import annotations

import pytest
from tests.fixtures.notifications import create_ready_report, make_eligible_contact

from secguard_advisor.notifications.confirmations import (
    create_confirmation,
    validate_confirmation,
)
from secguard_advisor.notifications.errors import NotificationError


def test_confirmation_validates_manifest(report_context) -> None:
    result = create_ready_report(report_context)
    contact, _ = make_eligible_contact(report_context)
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
        version, manifest, contact_ids = validate_confirmation(session, confirmation)
    assert version.status == "ready"
    assert contact_ids == [contact.id]
    assert manifest["manifest_sha256"] == confirmation.manifest_sha256


def test_confirmation_is_invalidated_by_recipient_change(report_context) -> None:
    result = create_ready_report(report_context)
    contact, _ = make_eligible_contact(report_context)
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
        persisted = session.get(type(contact), contact.id)
        persisted.alias = "Alias cambiado"
        session.flush()
        with pytest.raises(NotificationError) as error:
            validate_confirmation(session, confirmation)
        assert error.value.code == "manifest_mismatch"
        assert confirmation.invalidated_at is not None


def test_unverified_contact_cannot_be_confirmed(report_context) -> None:
    result = create_ready_report(report_context)
    from secguard_advisor.notifications.contacts import create_contact

    with report_context.session_factory() as session:
        contact = create_contact(session, alias="Sin verificar", chat_id="555555")
        session.flush()
        with pytest.raises(NotificationError):
            create_confirmation(
                session,
                case_id=report_context.case_id,
                report_id=result.report_id,
                version_number=result.version_number,
                contact_ids=[contact.id],
                created_by="Tester",
            )
