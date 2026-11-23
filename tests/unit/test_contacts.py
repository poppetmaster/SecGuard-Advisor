"""Contact lifecycle, consent and case links."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from secguard_advisor.db.models import ContactCaseLink, ContactChannel
from secguard_advisor.notifications.contacts import (
    create_contact,
    is_eligible,
    set_active,
    set_consent,
)
from secguard_advisor.notifications.errors import NotificationError


def test_new_contact_is_not_verified_consented_or_active(report_context) -> None:
    with report_context.session_factory() as session:
        contact = create_contact(
            session, alias="Operaciones", chat_id="123456789", chat_type="private"
        )
        session.commit()
        assert contact.status == "unverified"
        assert contact.consent_status == "pending"
        assert contact.active is False
        assert contact.verified_at is None


def test_duplicate_chat_is_rejected(report_context) -> None:
    with report_context.session_factory() as session:
        create_contact(session, alias="A", chat_id="123456789")
        with pytest.raises(NotificationError) as error:
            create_contact(session, alias="B", chat_id="123456789")
        assert error.value.code == "duplicate_contact"


def test_active_requires_verification_and_consent(report_context) -> None:
    with report_context.session_factory() as session:
        contact = create_contact(session, alias="A", chat_id="123456789")
        with pytest.raises(NotificationError):
            set_active(session, contact.id, True)
        contact.status = "verified"
        contact.verified_at = "2026-11-23T00:00:00+00:00"
        set_consent(session, contact.id, "granted", declared_by="Test")
        set_active(session, contact.id, True)
        session.commit()
        assert contact.active is True
        assert is_eligible(session, contact=contact, case_id=report_context.case_id) is False


def test_case_link_is_required_for_eligibility(report_context) -> None:
    with report_context.session_factory() as session:
        contact = create_contact(session, alias="A", chat_id="123456789")
        contact.status = "verified"
        contact.verified_at = "2026-11-23T00:00:00+00:00"
        set_consent(session, contact.id, "granted", declared_by="Test")
        set_active(session, contact.id, True)
        assert is_eligible(session, contact=contact, case_id=report_context.case_id) is False
        from secguard_advisor.notifications.contacts import authorize_case

        authorize_case(
            session, contact_id=contact.id, case_id=report_context.case_id, authorized=True
        )
        session.commit()
        assert is_eligible(session, contact=contact, case_id=report_context.case_id) is True
        assert session.scalar(select(ContactCaseLink)) is not None
        assert session.scalar(select(ContactChannel)) is not None
