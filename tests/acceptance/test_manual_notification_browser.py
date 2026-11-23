"""Browser acceptance for contacts and manual notification UI."""

from __future__ import annotations

import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from playwright.sync_api import sync_playwright
from tests.fixtures.notifications import create_ready_report, make_eligible_contact

from secguard_advisor.notifications.channels.telegram import StubTelegramTransport
from secguard_advisor.web.app import create_app

pytestmark = pytest.mark.integration
EVIDENCE = Path("docs/evidencia/006-corte-b")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_contacts_and_manual_send_browser(report_context) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    result = create_ready_report(report_context)
    contact, _ = make_eligible_contact(report_context, chat_id="123456789")
    transport = StubTelegramTransport()
    app = create_app(report_context.settings, ollama_probe=lambda: False)
    app.state.telegram_transport = transport
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    assert server.started
    base = f"http://127.0.0.1:{port}"
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.goto(f"{base}/settings/contacts", wait_until="networkidle")
            assert contact.alias in page.text_content("body")
            assert "••••" in page.text_content("body")
            assert "123456789" not in page.text_content("body")
            page.screenshot(path=str(EVIDENCE / "contacts-desktop.png"), full_page=True)

            url = (
                f"{base}/cases/{report_context.case_id}/reports/"
                f"{result.report_id}/versions/1/notifications"
            )
            page.goto(url, wait_until="networkidle")
            assert page.locator("input[name='contact_ids']").count() == 1
            assert page.locator("[data-form-key='manifest-confirm']").count() == 1
            page.fill("input[name='created_by']", "Guardia")
            page.click("button:has-text('Generar confirmación')")
            page.wait_for_url("**confirmation_id=**", timeout=30000)
            assert page.locator("[data-form-key='manual-send']").count() == 1
            assert "Contenido exacto" in page.text_content("body")
            page.screenshot(path=str(EVIDENCE / "manual-preview-desktop.png"), full_page=True)
            page.click("button:has-text('Confirmar y enviar')")
            page.wait_for_url("**/notifications", timeout=30000)
            assert "Aceptado por Telegram" in page.text_content("body")
            assert "no equivale a entregado" in page.text_content("body").lower()
            page.screenshot(path=str(EVIDENCE / "manual-history-desktop.png"), full_page=True)

            page.set_viewport_size({"width": 390, "height": 844})
            page.goto(f"{base}/settings/contacts", wait_until="networkidle")
            page.screenshot(path=str(EVIDENCE / "contacts-mobile.png"), full_page=True)
            page.click("#nav-toggle")
            assert page.locator("#mobile-nav").is_visible()
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=5)
