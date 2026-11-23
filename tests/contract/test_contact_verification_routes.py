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


def _create_verified_target(client, *, alias: str = "Guardia", chat_id: str = "123456789") -> str:
    client.post(
        "/settings/contacts",
        data={"alias": alias, "chat_id": chat_id, "chat_type": "private"},
        headers={"Origin": "http://testserver"},
        follow_redirects=False,
    )
    with client.app.state.session_factory() as session:
        return session.scalar(select(ContactChannel)).id


def _challenge_row(client):
    with client.app.state.session_factory() as session:
        return session.scalar(select(ContactVerificationChallenge))


def test_wrong_codes_persist_attempts_and_lock_across_requests(report_context) -> None:
    transport = StubTelegramTransport()
    with TestClient(create_app(report_context.settings, ollama_probe=lambda: False)) as client:
        client.app.state.telegram_transport = transport
        contact_id = _create_verified_target(client)
        client.post(
            f"/settings/contacts/{contact_id}/verification",
            headers={"Origin": "http://testserver"},
        )
        code = code_from_stub(transport)

        for attempt in (1, 2, 3):
            response = client.post(
                f"/settings/contacts/{contact_id}/verification/confirm",
                data={"code": "000000", "verified_by": "Tester"},
                headers={"Origin": "http://testserver"},
            )
            assert response.status_code == 422
            assert _challenge_row(client).attempts == attempt

        assert _challenge_row(client).status == "locked"
        with client.app.state.session_factory() as session:
            assert session.get(ContactChannel, contact_id).status == "unverified"

        with TestClient(create_app(report_context.settings, ollama_probe=lambda: False)) as fresh:
            fresh.app.state.telegram_transport = transport
            response = fresh.post(
                f"/settings/contacts/{contact_id}/verification/confirm",
                data={"code": code, "verified_by": "Tester"},
                headers={"Origin": "http://testserver"},
            )
            assert response.status_code == 422
            assert _challenge_row(fresh).status == "locked"
            with fresh.app.state.session_factory() as session:
                challenge = session.scalar(select(ContactVerificationChallenge))
                assert challenge.consumed_at is None
                assert session.get(ContactChannel, contact_id).status == "unverified"


def test_request_limit_persists_across_sessions(report_context) -> None:
    transport = StubTelegramTransport()
    with TestClient(create_app(report_context.settings, ollama_probe=lambda: False)) as client:
        client.app.state.telegram_transport = transport
        contact_id = _create_verified_target(client)
        for _ in range(3):
            response = client.post(
                f"/settings/contacts/{contact_id}/verification",
                headers={"Origin": "http://testserver"},
            )
            assert response.status_code == 200

    with TestClient(create_app(report_context.settings, ollama_probe=lambda: False)) as fresh:
        fresh.app.state.telegram_transport = transport
        response = fresh.post(
            f"/settings/contacts/{contact_id}/verification",
            headers={"Origin": "http://testserver"},
        )
        assert response.status_code == 422
        assert "límite" in response.text.lower()


def test_expired_challenge_is_persisted(report_context) -> None:
    from datetime import UTC, datetime, timedelta

    transport = StubTelegramTransport()
    with TestClient(create_app(report_context.settings, ollama_probe=lambda: False)) as client:
        client.app.state.telegram_transport = transport
        contact_id = _create_verified_target(client)
        client.post(
            f"/settings/contacts/{contact_id}/verification",
            headers={"Origin": "http://testserver"},
        )
        code = code_from_stub(transport)
        with client.app.state.session_factory() as session:
            challenge = session.scalar(select(ContactVerificationChallenge))
            challenge.expires_at = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
            session.commit()

        response = client.post(
            f"/settings/contacts/{contact_id}/verification/confirm",
            data={"code": code, "verified_by": "Tester"},
            headers={"Origin": "http://testserver"},
        )
        assert response.status_code == 422
        assert "expiró" in response.text.lower()
        assert _challenge_row(client).status == "expired"
        with client.app.state.session_factory() as session:
            assert session.get(ContactChannel, contact_id).status == "unverified"
