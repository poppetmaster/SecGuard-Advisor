"""Comprueba que el navegador local puede generar PDF con Playwright."""

from __future__ import annotations

import sys


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Falta playwright. Ejecutá `uv sync --locked`.")
        return 2
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(channel="chrome", headless=True)
                selected = "chrome"
            except Exception:
                browser = playwright.chromium.launch(headless=True)
                selected = "chromium"
            page = browser.new_page()
            page.set_content("<html><body><h1>PDF runtime</h1></body></html>")
            pdf = page.pdf(format="A4", print_background=True)
            browser.close()
    except Exception as exc:
        print(f"No se pudo iniciar el navegador para PDF: {exc}")
        return 1
    if not pdf.startswith(b"%PDF"):
        print("El navegador no devolvió un PDF válido.")
        return 1
    print(f"PDF runtime OK ({selected}, {len(pdf)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
