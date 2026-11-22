"""Aceptación de la interfaz con Qdrant y dobles rápidos (ASGI).

La regresión automatizada usa el cliente ASGI con almacenamiento temporal y el
índice Qdrant embebido. La verificación real en navegador (navegación, foco,
móvil, consola y recursos) se ejecuta con Playwright MCP contra el servidor y se
registra en `docs/evidencia/004-corte-6/`.

Uso de dobles:
- `FakeEmbedder`: vectores deterministas; no llama a Ollama.
- `ScriptedGenerator`: respuestas y decisiones guionizadas; no llama al modelo.
- `QdrantIndex`: índice embebido temporal con los vectores del doble.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from tests.fixtures.conversation import build_env
from tests.fixtures.fakes import FakeEmbedder, FakeTokenCounter, ScriptedGenerator

from secguard_advisor.conversation.llm import AnswerPayload, Claim, ToolDecision
from secguard_advisor.db.models import DocumentChunk
from secguard_advisor.retrieval.errors import QdrantUnavailable
from secguard_advisor.web.app import create_app

ORIGIN = {"Origin": "http://testserver"}
HTMX = {**ORIGIN, "HX-Request": "true"}
POLICY = (
    "# Política de respaldo\n\n"
    "La organización realiza copias de seguridad cifradas cada 24 horas y prueba la restauración "
    "trimestralmente. El responsable de infraestructura conserva el registro de cada prueba.\n"
)


class _UnavailableIndex:
    """Índice que falla como Qdrant caído en consulta y recuperación."""

    def query(self, *args, **kwargs):
        raise QdrantUnavailable("El índice documental no está disponible.")

    def query_with_identity(self, *args, **kwargs):
        raise QdrantUnavailable("El índice documental no está disponible.")


def _app(env, generator):
    return create_app(
        env.settings,
        ollama_probe=lambda: True,
        embedder_factory=lambda: FakeEmbedder(),
        index_factory=lambda: env.index,
        llm_factory=lambda: generator,
        token_counter=FakeTokenCounter(),
    )


def _generator() -> ScriptedGenerator:
    return ScriptedGenerator(
        payloads=[
            AnswerPayload(
                answer="La restauración se prueba trimestralmente.",
                claims=[
                    Claim(
                        text="La restauración se prueba trimestralmente.",
                        quote="prueba la restauración trimestralmente",
                    )
                ],
            )
        ],
        decisions=[ToolDecision(use_findings=False, arguments={})],
    )


def _create_case(client: TestClient, title: str) -> str:
    response = client.post("/cases", data={"title": title}, headers=ORIGIN, follow_redirects=False)
    assert response.status_code == 303
    return response.headers["location"].split("/")[-1]


def _upload_policy(client: TestClient, case_id: str) -> None:
    response = client.post(
        f"/cases/{case_id}/documents",
        files={"file": ("politica.md", POLICY.encode("utf-8"), "text/markdown")},
        data={"title": "Política de respaldo"},
        headers=HTMX,
    )
    assert response.status_code == 201
    assert "Disponible" in response.text


def test_navigation_and_sections_render(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False)
    with TestClient(_app(env, _generator())) as client:
        case_id = _create_case(client, "Caso de interfaz")

        listing = client.get("/cases")
        assert listing.status_code == 200
        assert "Caso de interfaz" in listing.text

        summary = client.get(f"/cases/{case_id}")
        assert summary.status_code == 200
        assert 'id="mobile-nav"' in summary.text
        assert 'aria-controls="mobile-nav"' in summary.text
        assert "/static/js/navigation.js" in summary.text
        assert "/static/js/forms.js" in summary.text

        for section in ("documents", "vulnerabilities", "chat"):
            page = client.get(f"/cases/{case_id}/{section}")
            assert page.status_code == 200, section
            assert "Caso de interfaz" in page.text
            assert 'aria-label="Navegación principal"' in page.text

        vulnerabilities = client.get(f"/cases/{case_id}/vulnerabilities")
        assert "Sin importaciones confirmadas" in vulnerabilities.text


def test_upload_query_citation_and_run_evidence(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    generator = _generator()
    with TestClient(_app(env, generator)) as client:
        case_id = _create_case(client, "Caso documental")
        documents = client.get(f"/cases/{case_id}/documents")
        assert documents.status_code == 200
        assert "Subir documento" in documents.text

        _upload_policy(client, case_id)
        generator.payloads[0].claims[0].chunk_ids = [_case_chunk_id(env)]

        answer = client.post(
            f"/cases/{case_id}/chat/messages",
            data={"question": "¿Cada cuánto se prueba la restauración?"},
            headers=HTMX,
        )
        assert answer.status_code == 200
        assert "La restauración se prueba trimestralmente." in answer.text
        assert "Abrir fragmento" in answer.text
        assert "Control automático (existencia y cita literal): válida" in answer.text
        assert "Ver ejecución" in answer.text

        locator = _first_match(
            answer.text, r'href="(/cases/[^"]+/documents/[^"]+/fragments/[^"]+)"'
        )
        fragment = client.get(locator)
        assert fragment.status_code == 200
        assert "<mark" in fragment.text

        run_link = _first_match(answer.text, r'href="(/cases/[^"]+/runs/[^"]+)"')
        evidence = client.get(run_link)
        assert evidence.status_code == 200
        assert "Control automático: válida" in evidence.text
        assert "Revisión humana:" in evidence.text


def test_loading_indicator_and_double_submit_markup(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False)
    with TestClient(_app(env, _generator())) as client:
        case_id = _create_case(client, "Caso de carga")
        chat = client.get(f"/cases/{case_id}/chat")
        assert chat.status_code == 200
        assert "data-pending-indicator" in chat.text
        assert "data-form-error" in chat.text
        assert "Consultando las fuentes y preparando la respuesta" in chat.text
        forms = client.get("/static/js/forms.js")
        assert forms.status_code == 200
        assert "htmx:beforeRequest" in forms.text
        assert "setPending" in forms.text


def test_index_failure_is_visible_and_not_silent(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False)
    with TestClient(_app(env, _generator())) as client:
        case_id = _create_case(client, "Caso con índice caído")
        _upload_policy(client, case_id)
        client.app.state.index_factory = lambda: _UnavailableIndex()

        failed = client.post(
            f"/cases/{case_id}/chat/messages",
            data={"question": "¿Cada cuánto se prueba la restauración?"},
            headers=HTMX,
        )
        assert failed.status_code == 503
        assert "El índice documental no está disponible." in failed.text
        assert "No encontré evidencia documental suficiente" not in failed.text


def _case_chunk_id(env) -> str:
    with env.factory() as session:
        chunk = session.scalar(
            select(DocumentChunk).where(DocumentChunk.text.contains("restauración"))
        )
        assert chunk is not None
        return chunk.id


def _first_match(html: str, pattern: str) -> str:
    return re.search(pattern, html).group(1)
