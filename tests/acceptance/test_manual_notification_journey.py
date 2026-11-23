"""Acceptance: contact, verification, confirmation and manual send with a stub."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from tests.fixtures.notifications import code_from_stub, create_ready_report

from secguard_advisor.db.models import ContactChannel, NotificationEvent
from secguard_advisor.notifications.channels.telegram import StubTelegramTransport
from secguard_advisor.web.app import create_app


def test_manual_notification_journey(report_context) -> None:
    result = create_ready_report(report_context)
    transport = StubTelegramTransport()
    with TestClient(create_app(report_context.settings, ollama_probe=lambda: False)) as client:
        client.app.state.telegram_transport = transport
        created = client.post(
            "/settings/contacts",
            data={"alias": "Guardia", "chat_id": "123456789", "chat_type": "private"},
            headers={"Origin": "http://testserver"},
        )
        assert created.status_code in {200, 303}
        with client.app.state.session_factory() as session:
            contact_id = session.scalar(select(ContactChannel)).id

        started = client.post(
            f"/settings/contacts/{contact_id}/verification",
            headers={"Origin": "http://testserver"},
        )
        assert "Código enviado" in started.text
        code = code_from_stub(transport)
        client.post(
            f"/settings/contacts/{contact_id}/verification/confirm",
            data={"code": code, "verified_by": "Guardia"},
            headers={"Origin": "http://testserver"},
        )
        client.post(
            f"/settings/contacts/{contact_id}/consent",
            data={"status": "granted", "declared_by": "Guardia"},
            headers={"Origin": "http://testserver"},
        )
        client.post(
            f"/settings/contacts/{contact_id}/status",
            data={"status": "verified", "active": "on"},
            headers={"Origin": "http://testserver"},
        )
        client.post(
            f"/cases/{report_context.case_id}/contacts/{contact_id}",
            data={"authorized": "on"},
            headers={"Origin": "http://testserver"},
        )

        url = f"/cases/{report_context.case_id}/reports/{result.report_id}/versions/1"
        preview = client.get(url + "/notifications")
        assert preview.status_code == 200
        assert "Guardia" in preview.text
        confirmed = client.post(
            url + "/confirmations",
            data={"contact_ids": [contact_id], "created_by": "Guardia"},
            headers={"Origin": "http://testserver"},
            follow_redirects=False,
        )
        assert confirmed.status_code == 303
        confirmation_id = confirmed.headers["location"].split("confirmation_id=")[-1]
        sent = client.post(
            url + "/notifications",
            data={"confirmation_id": confirmation_id},
            headers={"Origin": "http://testserver"},
            follow_redirects=False,
        )
        assert sent.status_code == 303
        history = client.get(f"/cases/{report_context.case_id}/notifications")
        assert history.status_code == 200
        assert "Aceptado por Telegram" in history.text
        with client.app.state.session_factory() as session:
            event = session.scalar(select(NotificationEvent))
            assert event.status == "accepted"
            assert event.idempotency_key
    assert any(call.method == "send_document" for call in transport.calls)
