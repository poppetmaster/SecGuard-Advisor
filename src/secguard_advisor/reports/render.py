"""Local chart and PDF rendering without CDN or external image services."""

from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from secguard_advisor.config import Settings
from secguard_advisor.reports.errors import report_error

_TEMPLATES = Path(__file__).resolve().parents[1] / "web" / "templates"
_CSS = Path(__file__).resolve().parents[1] / "web" / "static" / "css" / "app.css"
_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "render_report_charts.mjs"


def render_charts(settings: Settings, charts: dict) -> dict[str, str]:
    """Render every ECharts option to SVG using the local Node runtime."""
    options = {key: value["option"] for key, value in charts.items() if "option" in value}
    try:
        completed = subprocess.run(
            ["node", str(_SCRIPT)],
            input=json.dumps({"charts": options}),
            text=True,
            capture_output=True,
            check=True,
            timeout=60,
            cwd=str(_SCRIPT.parents[1]),
        )
        payload = json.loads(completed.stdout)
    except Exception as exc:
        raise report_error("charts_render_failed") from exc
    if set(payload) != set(options):
        raise report_error("charts_render_failed")
    return payload


def _data_uri(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def render_print_html(
    settings: Settings,
    *,
    dataset: dict,
    charts: dict,
    chart_svgs: dict[str, str],
    summary: dict,
) -> str:
    """Render the standalone print composition with inlined CSS and SVG charts."""
    environment = Environment(
        loader=FileSystemLoader(str(_TEMPLATES)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = environment.get_template("reports/print.html")
    css = _CSS.read_text(encoding="utf-8") if _CSS.exists() else ""
    return template.render(
        dataset=dataset,
        charts=charts,
        chart_images={key: _data_uri(svg) for key, svg in chart_svgs.items()},
        summary=summary,
        inline_css=css,
    )


def render_pdf(settings: Settings, html: str, output_path: Path) -> bytes:
    """Render HTML to an A4 PDF with the locally installed browser."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - environment gate
        raise report_error("pdf_render_failed") from exc
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.tmp")
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(channel="chrome", headless=True)
            except Exception:
                browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_content(html, wait_until="load")
            page.emulate_media(media="print")
            page.pdf(
                path=str(temporary),
                format="A4",
                print_background=True,
                margin={"top": "12mm", "bottom": "12mm", "left": "12mm", "right": "12mm"},
            )
            browser.close()
        content = temporary.read_bytes()
        temporary.replace(output_path)
        return content
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        raise report_error("pdf_render_failed") from exc
