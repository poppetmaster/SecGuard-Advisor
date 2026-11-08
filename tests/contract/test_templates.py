"""Pruebas de las plantillas base y de error."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATES = Path(__file__).resolve().parents[2] / "src" / "secguard_advisor" / "web" / "templates"


def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=True,
    )


def test_base_uses_only_local_resources() -> None:
    html = _environment().get_template("base.html").render()

    assert 'lang="es"' in html
    assert "/static/css/app.css" in html
    assert "/static/js/htmx.min.js" in html
    assert "/static/js/flowbite.min.js" in html
    assert "http://" not in html
    assert "https://" not in html


def test_error_partial_renders_message() -> None:
    html = (
        _environment()
        .get_template("partials/error.html")
        .render(message="No encontrado en este caso.")
    )

    assert "No encontrado en este caso." in html
    assert 'role="alert"' in html
