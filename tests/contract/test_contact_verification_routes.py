"""Contact and verification routes, independent from report eligibility."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from tests.fixtures.notifications import code_from_stub

from secguard_advisor.db.models import ContactChannel, ContactVerificationChallenge
from secguard_advisor.notifications.channels.telegram import StubTelegramTransport
from secguard_advisor.web.app import create_app


def test_contact_verification_route_flow_without_report(report_context) -> None:
    transport = StubTelegramTransport()
    with TestClient(create_app(report_context.settings, ollama_probe=lambda: False)) as client:
        client.app.state.telegram_transport = transport
        created = client.post(
            "/settings/contacts",
            data={"alias": "Operaciones", "chat_id": "123456789", "chat_type": "private"},
            headers={"Origin": "http://testserver"},
            follow_redirects=False,
        )
        assert created.status_code == 303
        with client.app.state.session_factory() as session:
            contact = session.scalar(select(ContactChannel))
            contact_id = contact.id
            assert contact.status == "unverified"
            assert contact.consent_status == "pending"
            assert contact.active is False

        started = client.post(
            f"/settings/contacts/{contact_id}/verification",
            headers={"Origin": "http://testserver"},
        )
        assert started.status_code == 200
        assert "Código enviado" in started.text
        code = code_from_stub(transport)

        confirmed = client.post(
            f"/settings/contacts/{contact_id}/verification/confirm",
            data={"code": code, "verified_by": "Tester"},
            headers={"Origin": "http://testserver"},
        )
        assert confirmed.status_code == 200
        assert "verificado" in confirmed.text.lower()

        consented = client.post(
            f"/settings/contacts/{contact_id}/consent",
            data={"status": "granted", "declared_by": "Tester"},
            headers={"Origin": "http://testserver"},
        )
        assert consented.status_code == 200
        activated = client.post(
            f"/settings/contacts/{contact_id}/status",
            data={"status": "verified", "active": "on"},
            headers={"Origin": "http://testserver"},
        )
        assert activated.status_code == 200
        linked = client.post(
            f"/cases/{report_context.case_id}/contacts/{contact_id}",
            data={"authorized": "on"},
            headers={"Origin": "http://testserver"},
        )
        assert linked.status_code == 200
        with client.app.state.session_factory() as session:
            contact = session.get(ContactChannel, contact_id)
            assert contact.status == "verified"
            assert contact.consent_status == "granted"
            assert contact.active is True
            assert session.scalar(select(ContactVerificationChallenge)).status == "consumed"
        page = client.get("/settings/contacts")
        assert "Operaciones" in page.text
        assert "123456789" not in page.text


def test_bad_code_keeps_contact_unverified(report_context) -> None:
    transport = StubTelegramTransport()
    with TestClient(create_app(report_context.settings, ollama_probe=lambda: False)) as client:
        client.app.state.telegram_transport = transport
        client.post(
            "/settings/contacts",
            data={"alias": "Ops", "chat_id": "123456789"},
            headers={"Origin": "http://testserver"},
        )
        with client.app.state.session_factory() as session:
            contact_id = session.scalar(select(ContactChannel)).id
        client.post(
            f"/settings/contacts/{contact_id}/verification",
            headers={"Origin": "http://testserver"},
        )
        response = client.post(
            f"/settings/contacts/{contact_id}/verification/confirm",
            data={"code": "000000", "verified_by": "Tester"},
            headers={"Origin": "http://testserver"},
        )
        assert response.status_code == 422
        with client.app.state.session_factory() as session:
            assert session.get(ContactChannel, contact_id).status == "unverified"
