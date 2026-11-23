"""Manual delivery routes and manifest mismatch."""

from __future__ import annotations

from fastapi.testclient import TestClient
from tests.fixtures.notifications import create_ready_report, make_eligible_contact

from secguard_advisor.db.models import ContactChannel
from secguard_advisor.notifications.channels.telegram import StubTelegramTransport
from secguard_advisor.web.app import create_app


def test_manual_delivery_route_flow(report_context) -> None:
    result = create_ready_report(report_context)
    contact, _ = make_eligible_contact(report_context)
    send_transport = StubTelegramTransport()
    with TestClient(create_app(report_context.settings, ollama_probe=lambda: False)) as client:
        client.app.state.telegram_transport = send_transport
        url = f"/cases/{report_context.case_id}/reports/{result.report_id}/versions/1"
        preview = client.get(url + "/notifications")
        assert preview.status_code == 200
        assert "Destinatarios" in preview.text
        assert contact.alias in preview.text
        assert "123456789" not in preview.text

        confirmed = client.post(
            url + "/confirmations",
            data={"contact_ids": [contact.id], "created_by": "Tester"},
            headers={"Origin": "http://testserver"},
            follow_redirects=False,
        )
        assert confirmed.status_code == 303
        confirmation_id = confirmed.headers["location"].split("confirmation_id=")[-1]
        confirm_page = client.get(confirmed.headers["location"])
        assert confirm_page.status_code == 200
        assert "Confirmar y enviar" in confirm_page.text
        assert "Manifiesto" in confirm_page.text

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
        assert "no equivale a entregado" in history.text.lower()


def test_manifest_mismatch_returns_409(report_context) -> None:
    result = create_ready_report(report_context)
    contact, _ = make_eligible_contact(report_context)
    transport = StubTelegramTransport()
    with TestClient(create_app(report_context.settings, ollama_probe=lambda: False)) as client:
        client.app.state.telegram_transport = transport
        url = f"/cases/{report_context.case_id}/reports/{result.report_id}/versions/1"
        confirmed = client.post(
            url + "/confirmations",
            data={"contact_ids": [contact.id], "created_by": "Tester"},
            headers={"Origin": "http://testserver"},
            follow_redirects=False,
        )
        confirmation_id = confirmed.headers["location"].split("confirmation_id=")[-1]
        with client.app.state.session_factory() as session:
            stored = session.get(ContactChannel, contact.id)
            stored.alias = "Alias cambiado"
            session.commit()
        response = client.post(
            url + "/notifications",
            data={"confirmation_id": confirmation_id},
            headers={"Origin": "http://testserver"},
            follow_redirects=False,
        )
        assert response.status_code == 409
        assert "manifiesto" in response.text.lower() or "contenido" in response.text.lower()
        assert transport.calls == []


def test_invalid_contact_returns_422(report_context) -> None:
    result = create_ready_report(report_context)
    with TestClient(create_app(report_context.settings, ollama_probe=lambda: False)) as client:
        url = f"/cases/{report_context.case_id}/reports/{result.report_id}/versions/1"
        response = client.post(
            url + "/confirmations",
            data={"contact_ids": ["inexistente"], "created_by": "Tester"},
            headers={"Origin": "http://testserver"},
            follow_redirects=False,
        )
        assert response.status_code == 422
