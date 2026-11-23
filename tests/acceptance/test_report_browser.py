"""Browser acceptance for the executive report (desktop and mobile)."""

from __future__ import annotations

import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from playwright.sync_api import sync_playwright

from secguard_advisor.web.app import create_app

pytestmark = pytest.mark.integration

EVIDENCE = Path("docs/evidencia/006-corte-a")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_report_browser_desktop_mobile_and_pdf(report_context) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    port = _free_port()
    app = create_app(report_context.settings, ollama_probe=lambda: False)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    assert server.started
    base = f"http://127.0.0.1:{port}"
    console_errors: list[str] = []
    failed_requests: list[str] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.on(
                "console",
                lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
            )
            page.on("requestfailed", lambda request: failed_requests.append(request.url))

            page.goto(f"{base}/cases/{report_context.case_id}/reports", wait_until="networkidle")
            assert "Informe ejecutivo" in page.title() or "Informe" in page.text_content("body")
            page.click("text=Generar informe")
            page.wait_for_url("**/reports/new")
            assert page.locator("[data-form-key='report-generate']").count() == 1
            assert page.locator("[data-pending-text]").count() == 1
            page.fill("input[name='author']", "Revisión de navegador")
            page.click("button[type=submit]")
            page.wait_for_url("**/versions/1", timeout=30000)
            page.wait_for_load_state("networkidle")
            assert page.locator("#chart-severity canvas").count() == 1
            assert page.locator("#chart-assets canvas").count() == 1
            assert page.locator("details").count() >= 4
            page.screenshot(path=str(EVIDENCE / "browser-desktop.png"), full_page=True)

            with page.expect_download() as download_info:
                page.click("text=Descargar PDF")
            download = download_info.value
            pdf_path = EVIDENCE / "pdf-muestra.pdf"
            download.save_as(str(pdf_path))
            assert pdf_path.read_bytes().startswith(b"%PDF")

            page.set_viewport_size({"width": 390, "height": 844})
            page.reload(wait_until="networkidle")
            page.screenshot(path=str(EVIDENCE / "browser-mobile.png"), full_page=True)
            assert page.locator("#nav-toggle").is_visible()
            page.click("#nav-toggle")
            assert page.locator("#mobile-nav").is_visible()
            page.screenshot(path=str(EVIDENCE / "browser-mobile-nav.png"), full_page=True)
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=5)
    assert console_errors == []
    assert [url for url in failed_requests if not url.endswith("/pdf")] == []
