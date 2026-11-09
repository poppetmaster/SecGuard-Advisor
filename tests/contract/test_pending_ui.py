"""Contrato de la interfaz: estados pendientes, errores visibles y accesibilidad."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from tests.fixtures.corpus import create_case, seed_document
from tests.fixtures.fakes import FakeEmbedder, FakeTokenCounter, ScriptedGenerator

from secguard_advisor.config import Settings
from secguard_advisor.conversation.llm import AnswerPayload, Claim
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import MessageCitation
from secguard_advisor.retrieval.index import ChromaIndex
from secguard_advisor.web.app import create_app

ORIGIN = {"Origin": "http://testserver"}
HTMX = {**ORIGIN, "HX-Request": "true"}
TEXT = "El marco define seis funciones centrales de ciberseguridad."


def _settings(tmp_path: Path, *, reviewer: str | None = None) -> Settings:
    return Settings(
        _env_file=None,
        storage_dir=tmp_path / "storage",
        reviewer_name=reviewer,
    )


def _app(settings: Settings, index, generator):
    return create_app(
        settings,
        ollama_probe=lambda: True,
        embedder_factory=lambda: FakeEmbedder(),
        index_factory=lambda: index,
        llm_factory=lambda: generator,
        token_counter=FakeTokenCounter(),
    )


def _prepare(settings: Settings) -> None:
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    engine.dispose()


def _seeded(tmp_path: Path, *, reviewer: str | None = None):
    settings = _settings(tmp_path, reviewer=reviewer)
    _prepare(settings)
    index = ChromaIndex(tmp_path / "chroma")
    engine = create_engine_for_url(settings.database_url)
    factory = create_session_factory(engine)
    with factory() as session:
        case_id = create_case(session, "Caso de interfaz")
        session.commit()
    document = seed_document(
        factory,
        texts=[TEXT],
        index=index,
        embedder=FakeEmbedder(),
        case_id=case_id,
        pages=[3],
    )
    generator = ScriptedGenerator(
        payloads=[
            AnswerPayload(
                answer="El marco define seis funciones.",
                claims=[
                    Claim(
                        text="Afirmación",
                        chunk_ids=[document.chunk_ids[0]],
                        quote="seis funciones centrales",
                    )
                ],
            )
        ]
    )
    return settings, factory, case_id, document, index, generator


def test_chat_form_declares_pending_state(tmp_path: Path) -> None:
    settings, _factory, case_id, _document, index, generator = _seeded(tmp_path)
    app = _app(settings, index, generator)

    with TestClient(app) as client:
        page = client.get(f"/cases/{case_id}/chat")

    assert page.status_code == 200
    html = page.text
    assert 'data-form-key="chat-question"' in html
    assert "data-pending-indicator" in html
    assert 'role="status"' in html
    assert 'aria-live="polite"' in html
    assert "Consultando las fuentes y preparando la respuesta…" in html
    assert "disabled:cursor-not-allowed" in html
    assert "disabled:bg-slate-400" in html
    assert "/static/js/forms.js" in html


def test_document_forms_declare_pending_state(tmp_path: Path) -> None:
    settings, factory, case_id, _document, index, generator = _seeded(tmp_path)
    failed = seed_document(
        factory,
        texts=["contenido fallido"],
        index=index,
        embedder=FakeEmbedder(),
        case_id=case_id,
        pages=[1],
        version_status="failed",
        current=False,
    )
    app = _app(settings, index, generator)

    with TestClient(app) as client:
        panel = client.get(f"/cases/{case_id}/documents")
        detail = client.get(f"/cases/{case_id}/documents/{failed.document_id}")

    assert 'data-form-key="document-upload"' in panel.text
    assert "Enviando y procesando el documento…" in panel.text
    assert "Volvé a seleccionar el archivo" not in panel.text
    assert 'data-form-key="document-retry"' in detail.text
    assert "Reintentando el procesamiento del documento…" in detail.text


def test_review_form_declares_pending_state_and_contrast(tmp_path: Path) -> None:
    settings, factory, case_id, _document, index, generator = _seeded(
        tmp_path, reviewer="Revisora Local"
    )
    app = _app(settings, index, generator)

    with TestClient(app) as client:
        response = client.post(
            f"/cases/{case_id}/chat/messages",
            data={"question": "¿Qué funciones define?"},
            headers=HTMX,
        )
        page = client.get(f"/cases/{case_id}/chat")

    assert response.status_code == 200
    html = page.text
    assert 'data-form-key="citation-review-' in html
    assert "Guardando revisión…" in html
    assert "bg-slate-900" in html
    assert "disabled:text-slate-900" in html
    assert "Revisión no disponible" not in html
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(MessageCitation)) == 1


def test_review_without_identity_shows_reason(tmp_path: Path) -> None:
    settings, _factory, case_id, _document, index, generator = _seeded(tmp_path)
    app = _app(settings, index, generator)

    with TestClient(app) as client:
        client.post(
            f"/cases/{case_id}/chat/messages",
            data={"question": "¿Qué funciones define?"},
            headers=HTMX,
        )
        page = client.get(f"/cases/{case_id}/chat")

    assert "Revisión no disponible" in page.text
    assert "SECGUARD_REVIEWER_NAME" in page.text
    assert "Registrar revisión" not in page.text


def test_validation_error_panel_is_swappable(tmp_path: Path) -> None:
    settings, _factory, case_id, _document, index, generator = _seeded(tmp_path)
    app = _app(settings, index, generator)

    with TestClient(app) as client:
        chat_error = client.post(
            f"/cases/{case_id}/chat/messages",
            data={"question": "   "},
            headers=HTMX,
        )
        document_error = client.post(
            f"/cases/{case_id}/documents",
            files={"file": ("script.exe", b"contenido", "application/octet-stream")},
            headers=HTMX,
        )

    assert chat_error.status_code == 422
    assert chat_error.text.lstrip().startswith('<section id="chat-panel"')
    assert document_error.status_code == 415
    assert document_error.text.lstrip().startswith('<section id="documents-panel"')
    assert "Solo se admiten PDF" in document_error.text


def test_review_errors_return_the_citation_fragment(tmp_path: Path) -> None:
    settings, factory, case_id, _document, index, generator = _seeded(tmp_path)
    app = _app(settings, index, generator)

    with TestClient(app) as client:
        client.post(
            f"/cases/{case_id}/chat/messages",
            data={"question": "¿Qué funciones define?"},
            headers=HTMX,
        )
        with factory() as session:
            citation = session.scalar(select(MessageCitation))
            citation_id = citation.id
            message_id = citation.message_id
        missing_identity = client.post(
            f"/cases/{case_id}/messages/{message_id}/citations/{citation_id}/review",
            data={"status": "supported", "note": ""},
            headers=HTMX,
        )

    assert missing_identity.status_code == 409
    assert missing_identity.text.lstrip().startswith('<div id="citation-')
    assert "SECGUARD_REVIEWER_NAME" in missing_identity.text or "Revisión no disponible" in (
        missing_identity.text
    )


def test_forms_script_is_served(tmp_path: Path) -> None:
    settings, _factory, _case_id, _document, index, generator = _seeded(tmp_path)
    app = _app(settings, index, generator)

    with TestClient(app) as client:
        script = client.get("/static/js/forms.js")

    assert script.status_code == 200
    body = script.text
    for marker in (
        "htmx:beforeRequest",
        "htmx:beforeSwap",
        "htmx:afterRequest",
        "htmx:sendError",
        "htmx:timeout",
        "aria-busy",
        "data-pending-indicator",
    ):
        assert marker in body
