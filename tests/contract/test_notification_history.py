"""Notification history states and masking."""

from __future__ import annotations

from fastapi.testclient import TestClient
from tests.fixtures.notifications import create_ready_report, make_eligible_contact

from secguard_advisor.notifications.channels.telegram import StubTelegramTransport
from secguard_advisor.web.app import create_app


def test_history_shows_recipient_component_states_and_masks(report_context) -> None:
    result = create_ready_report(report_context)
    contact, _ = make_eligible_contact(report_context, chat_id="987654321")
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
        client.post(
            url + "/notifications",
            data={"confirmation_id": confirmation_id},
            headers={"Origin": "http://testserver"},
            follow_redirects=False,
        )
        history = client.get(f"/cases/{report_context.case_id}/notifications")
        assert history.status_code == 200
        assert contact.alias in history.text
        assert "••••" in history.text
        assert "987654321" not in history.text
        assert "Aceptado por Telegram" in history.text
        assert "summary" not in history.text.lower() or "Resumen" in history.text
        assert "no equivale a entregado" in history.text.lower()
        assert "no equivale a entregado" in history.text.lower()
