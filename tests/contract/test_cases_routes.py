"""Pruebas de contrato de las rutas de casos."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url
from secguard_advisor.web.app import create_app

ORIGIN = {"Origin": "http://testserver"}


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, storage_dir=tmp_path / "storage")


@pytest.fixture
def client(settings: Settings):
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    engine.dispose()
    app = create_app(settings, ollama_probe=lambda: True)
    with TestClient(app) as test_client:
        yield test_client


def _create(client: TestClient, **overrides: str):
    data = {
        "title": "Evaluación de un asistente",
        "description": "Contexto educativo sintético",
        "ai_application": "Asistente interno",
        "data_processed": "Documentos públicos",
        "restrictions": "Sin datos reales",
        "assets": "api-gateway\nportal",
    }
    data.update(overrides)
    return client.post("/cases", data=data, headers=ORIGIN, follow_redirects=False)


def test_empty_list(client) -> None:
    response = client.get("/cases")

    assert response.status_code == 200
    assert "Todavía no hay casos" in response.text


def test_root_redirects_to_cases(client) -> None:
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/cases"


def test_new_form(client) -> None:
    response = client.get("/cases/new")

    assert response.status_code == 200
    assert 'name="title"' in response.text
    assert 'name="assets"' in response.text


def test_create_redirects_and_detail(client) -> None:
    response = _create(client)

    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("/cases/")

    detail = client.get(location)
    assert detail.status_code == 200
    assert "Evaluación de un asistente" in detail.text
    assert "Contexto educativo sintético" in detail.text
    assert "api-gateway" in detail.text
    assert "portal" in detail.text
    assert "Escenario educativo sintético" in detail.text

    listing = client.get("/cases")
    assert "Evaluación de un asistente" in listing.text


def test_title_is_required(client) -> None:
    response = _create(client, title="   ")

    assert response.status_code == 422
    assert "El título es obligatorio." in response.text
    assert "Todavía no hay casos" in client.get("/cases").text


def test_long_title_is_rejected(client) -> None:
    response = _create(client, title="x" * 201)

    assert response.status_code == 422
    assert "200 caracteres" in response.text


def test_long_asset_is_rejected(client) -> None:
    response = _create(client, assets="x" * 121)

    assert response.status_code == 422
    assert "120 caracteres" in response.text


def test_post_without_origin_is_rejected(client) -> None:
    response = client.post("/cases", data={"title": "Caso"})

    assert response.status_code == 403
    assert "no proviene de esta aplicación" in response.text


def test_unknown_case_returns_404(client) -> None:
    response = client.get(f"/cases/{'0' * 32}")

    assert response.status_code == 404
    assert "No encontrado" in response.text


def test_list_only_shows_its_own_cases(client) -> None:
    first = _create(client, title="Caso A")
    second = _create(client, title="Caso B")
    first_id = first.headers["location"]
    second_id = second.headers["location"]

    second_detail = client.get(second_id)

    assert "Caso B" in second_detail.text
    assert "Caso A" not in second_detail.text
    assert first_id != second_id


def test_user_content_is_escaped(client) -> None:
    response = _create(client, description="<script>alert(1)</script>")
    detail = client.get(response.headers["location"])

    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in detail.text
    assert "<script>alert(1)</script>" not in detail.text
