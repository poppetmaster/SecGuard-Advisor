"""Contrato de navegación: barra lateral, secciones y rutas de presentación."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from tests.fixtures.corpus import create_case, seed_document
from tests.fixtures.fakes import FakeEmbedder

from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.retrieval.index import ChromaIndex
from secguard_advisor.web.app import create_app

ORIGIN = {"Origin": "http://testserver"}
HTMX = {**ORIGIN, "HX-Request": "true"}

SECTIONS = {
    "summary": "Resumen",
    "documents": "Documentos",
    "chat": "Consulta documental",
}


@pytest.fixture
def context(tmp_path: Path):
    settings = Settings(_env_file=None, storage_dir=tmp_path / "storage")
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        case_id = create_case(session, "Caso de navegación")
        session.commit()
    index = ChromaIndex(tmp_path / "chroma")
    document = seed_document(
        factory,
        texts=["Fragmento de prueba para la navegación."],
        index=index,
        embedder=FakeEmbedder(),
        case_id=case_id,
        pages=[2],
    )
    app = create_app(
        settings,
        ollama_probe=lambda: True,
        embedder_factory=lambda: FakeEmbedder(),
        index_factory=lambda: index,
    )
    with TestClient(app) as client:
        yield client, factory, case_id, document
    engine.dispose()


def _aside(html: str) -> str:
    match = re.search(r"<aside[^>]*>(.*?)</aside>", html, re.DOTALL)
    assert match is not None
    return match.group(1)


def test_general_group_and_no_case_options_without_case(context) -> None:
    client, _factory, _case_id, _document = context

    page = client.get("/cases")
    html = page.text

    assert page.status_code == 200
    assert "General" in html
    assert "Caso abierto" not in html
    assert 'href="/cases"' in html and 'href="/cases/new"' in html
    assert 'href="/cases//' not in html
    assert 'aria-current="page"' in _aside(html)


def test_case_group_is_visible_and_marks_the_active_section(context) -> None:
    client, _factory, case_id, _document = context

    page = client.get(f"/cases/{case_id}")
    html = page.text
    aside = _aside(html)

    assert "Caso abierto" in html
    assert "Caso de navegación" in aside
    assert f'href="/cases/{case_id}"' in aside
    assert f'href="/cases/{case_id}/documents"' in aside
    assert f'href="/cases/{case_id}/chat"' in aside
    assert aside.count('aria-current="page"') == 1
    summary_link = re.search(rf'<a\s+href="/cases/{case_id}"\s+aria-current="page"', aside)
    assert summary_link is not None
    assert "<h1" in html and "Resumen" in html


def test_each_section_is_directly_addressable_and_keeps_its_place(context) -> None:
    client, _factory, case_id, _document = context

    expected = {
        f"/cases/{case_id}": "Resumen",
        f"/cases/{case_id}/documents": "Documentos",
        f"/cases/{case_id}/chat": "Consulta documental",
        "/cases/new": "Nuevo caso",
        "/cases": "Casos",
    }
    for url, title in expected.items():
        page = client.get(url)
        assert page.status_code == 200, url
        assert (
            f'<h1 class="mt-3 text-2xl font-semibold tracking-tight text-slate-900">{title}</h1>'
            in page.text
        ), url
        aside = _aside(page.text)
        assert aside.count('aria-current="page"') == 1, url


def test_summary_does_not_render_other_sections(context) -> None:
    client, _factory, case_id, _document = context

    html = client.get(f"/cases/{case_id}").text

    assert 'id="documents-panel"' not in html
    assert 'id="chat-panel"' not in html
    assert "Activos relevantes" in html


def test_documents_fragment_does_not_render_the_shell(context) -> None:
    client, _factory, case_id, _document = context

    page = client.get(f"/cases/{case_id}/documents", headers={"HX-Request": "true"})

    assert page.status_code == 200
    assert page.text.lstrip().startswith('<section id="documents-panel"')
    assert "<aside" not in page.text
    assert "<header" not in page.text


def test_breadcrumbs_follow_the_case(context) -> None:
    client, _factory, case_id, _document = context

    html = client.get(f"/cases/{case_id}/chat").text

    assert "Ruta de navegación" in html
    assert "Casos" in html
    assert "Caso de navegación" in html
    assert "Consulta documental" in html


def test_document_and_fragment_keep_the_case_and_section(context) -> None:
    client, _factory, case_id, document = context

    detail = client.get(f"/cases/{case_id}/documents/{document.document_id}")
    fragment = client.get(
        f"/cases/{case_id}/documents/{document.document_id}"
        f"/versions/{document.version_id}/fragments/{document.chunk_ids[0]}"
    )

    for page in (detail, fragment):
        assert page.status_code == 200
        assert "Caso de navegación" in page.text
        aside = _aside(page.text)
        assert aside.count('aria-current="page"') == 1
        assert 'aria-current="page"' in aside
        assert "Documentos" in aside
    assert "Volver a documentos" in detail.text


def test_fragment_back_link_is_built_by_the_server(context) -> None:
    client, _factory, case_id, document = context
    base = (
        f"/cases/{case_id}/documents/{document.document_id}"
        f"/versions/{document.version_id}/fragments/{document.chunk_ids[0]}"
    )

    with_origin = client.get(base, params={"from": "consultation"})
    without_origin = client.get(base)
    hostile = client.get(base, params={"from": "https://example.test/steal"})

    assert f'href="/cases/{case_id}/chat"' in with_origin.text
    assert "Volver a la consulta" in with_origin.text
    assert "Volver a la consulta" not in without_origin.text
    assert "example.test" not in hostile.text
    assert "Volver a la consulta" not in hostile.text


def test_other_case_resources_stay_hidden(context) -> None:
    client, factory, _case_id, document = context
    with factory() as session:
        other_id = create_case(session, "Otro caso")
        session.commit()

    detail = client.get(f"/cases/{other_id}/documents/{document.document_id}")
    documents = client.get(f"/cases/{other_id}/documents")
    chat = client.get(f"/cases/{other_id}/chat")

    assert detail.status_code == 404
    assert documents.status_code == 200
    assert document.document_id not in documents.text
    assert chat.status_code == 200
    assert "Otro caso" in chat.text


def test_long_case_names_do_not_break_the_sidebar(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, storage_dir=tmp_path / "storage")
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    long_title = ("Caso con un nombre extraordinariamente largo " * 4).strip()
    with factory() as session:
        case_id = create_case(session, long_title)
        session.commit()
    app = create_app(settings, ollama_probe=lambda: True)
    try:
        with TestClient(app) as client:
            html = client.get(f"/cases/{case_id}").text
    finally:
        engine.dispose()

    aside = _aside(html)
    assert "truncate" in aside
    assert f'title="{long_title}"' in aside


def test_pages_use_only_local_resources(context) -> None:
    client, _factory, case_id, _document = context

    for url in (f"/cases/{case_id}", f"/cases/{case_id}/chat", "/cases"):
        html = client.get(url).text
        assert "http://" not in html
        assert "https://" not in html
        assert "/static/css/app.css" in html
        assert "/static/js/navigation.js" in html
        assert "/static/js/forms.js" in html


def test_public_corpus_citation_fragment_opens(context) -> None:
    client, factory, case_id, _document = context
    public = seed_document(
        factory,
        texts=["Guía pública de prueba para citas."],
        source_id="csf2",
        pages=[4],
    )

    page = client.get(
        f"/cases/{case_id}/documents/{public.document_id}"
        f"/versions/{public.version_id}/fragments/{public.chunk_ids[0]}",
        params={"from": "consultation"},
    )

    assert page.status_code == 200
    assert "Corpus público" in page.text
    assert "Volver a la consulta" in page.text
    assert 'aria-current="page"' in _aside(page.text)


def test_header_uses_the_approved_decorative_icon(context) -> None:
    client, _factory, _case_id, _document = context

    html = client.get("/cases").text

    assert 'src="/static/icons/secguard-icon.svg"' in html
    assert 'alt=""' in html
    assert 'aria-hidden="true"' in html
    assert 'href="/static/icons/secguard-icon.svg"' in html
    assert 'href="/static/icons/favicon.ico"' in html
    assert 'href="/static/icons/secguard-icon-512.png"' in html
    assert "/static/favicon.svg" not in html


def test_icon_resources_are_served_locally(context) -> None:
    client, _factory, _case_id, _document = context

    svg = client.get("/static/icons/secguard-icon.svg")
    ico = client.get("/static/icons/favicon.ico")
    png = client.get("/static/icons/secguard-icon-512.png")

    assert svg.status_code == 200
    assert "image/svg+xml" in svg.headers["content-type"]
    assert "<svg" in svg.text
    assert ico.status_code == 200
    assert png.status_code == 200


def test_fragment_highlights_a_quote_with_normalized_whitespace(context) -> None:
    client, factory, case_id, _document = context
    seeded = seed_document(
        factory,
        texts=["El marco define funciones centrales:\n  gobernar,   identificar y proteger."],
        case_id=case_id,
        pages=[7],
    )
    base = (
        f"/cases/{case_id}/documents/{seeded.document_id}"
        f"/versions/{seeded.version_id}/fragments/{seeded.chunk_ids[0]}"
    )

    highlighted = client.get(base, params={"quote": "centrales: gobernar, identificar"})
    missing = client.get(base, params={"quote": "una frase que no está"})

    assert highlighted.status_code == 200
    assert "<mark" in highlighted.text
    assert "centrales:\n  gobernar,   identificar" in highlighted.text
    assert missing.status_code == 200
    assert "<mark" not in missing.text
