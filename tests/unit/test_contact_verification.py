"""Hashed verification challenges, limits and consumption."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from tests.fixtures.notifications import code_from_stub

from secguard_advisor.db.models import ContactChannel, ContactVerificationChallenge
from secguard_advisor.notifications.channels.telegram import StubTelegramTransport
from secguard_advisor.notifications.contacts import create_contact
from secguard_advisor.notifications.errors import NotificationError
from secguard_advisor.notifications.verification import (
    confirm_verification,
    start_verification,
)


def _contact(factory):
    with factory() as session:
        contact = create_contact(session, alias="Prueba", chat_id="123456789")
        session.commit()
        return contact.id


def test_code_is_hashed_and_verification_is_independent(report_context) -> None:
    transport = StubTelegramTransport()
    with report_context.session_factory() as session:
        contact_id = _contact(report_context.session_factory)
        challenge = start_verification(session, contact_id=contact_id, transport=transport)
        session.commit()
        assert challenge.status == "pending"
        assert challenge.code_sha256 != code_from_stub(transport)
        assert len(challenge.code_sha256) == 64
        contact = session.get(ContactChannel, contact_id)
        assert contact.status == "unverified"
        # No consent or case link is required to request the code.
        assert contact.consent_status == "pending"
        assert transport.calls[-1].method == "send_message"


def test_wrong_attempts_lock_the_challenge(report_context) -> None:
    transport = StubTelegramTransport()
    with report_context.session_factory() as session:
        contact_id = _contact(report_context.session_factory)
        start_verification(session, contact_id=contact_id, transport=transport)
        session.commit()
        for _ in range(3):
            with pytest.raises(NotificationError):
                confirm_verification(session, contact_id=contact_id, code="000000", verified_by="X")
        challenge = session.scalar(select(ContactVerificationChallenge))
        assert challenge.status == "locked"
        with pytest.raises(NotificationError) as error:
            confirm_verification(session, contact_id=contact_id, code="000000", verified_by="X")
        assert error.value.code == "code_consumed"


def test_expired_code_is_rejected(report_context) -> None:
    transport = StubTelegramTransport()
    with report_context.session_factory() as session:
        contact_id = _contact(report_context.session_factory)
        challenge = start_verification(session, contact_id=contact_id, transport=transport)
        challenge.expires_at = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
        session.commit()
        with pytest.raises(NotificationError) as error:
            confirm_verification(
                session, contact_id=contact_id, code=code_from_stub(transport), verified_by="X"
            )
        assert error.value.code == "code_expired"


def test_successful_code_verifies_contact_and_consumes_challenge(report_context) -> None:
    transport = StubTelegramTransport()
    with report_context.session_factory() as session:
        contact_id = _contact(report_context.session_factory)
        start_verification(session, contact_id=contact_id, transport=transport)
        session.commit()
        contact = confirm_verification(
            session, contact_id=contact_id, code=code_from_stub(transport), verified_by="Tester"
        )
        session.commit()
        assert contact.status == "verified"
        assert contact.verified_by == "Tester"
        assert session.scalar(select(ContactVerificationChallenge)).status == "consumed"


def test_request_limit_is_enforced(report_context) -> None:
    transport = StubTelegramTransport()
    with report_context.session_factory() as session:
        contact_id = _contact(report_context.session_factory)
        for _ in range(3):
            start_verification(session, contact_id=contact_id, transport=transport)
            session.commit()
        with pytest.raises(NotificationError) as error:
            start_verification(session, contact_id=contact_id, transport=transport)
        assert error.value.code == "rate_limited"
