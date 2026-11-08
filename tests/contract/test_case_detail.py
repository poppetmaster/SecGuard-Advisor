"""Pruebas de la vista de detalle de un caso."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url
from secguard_advisor.web.app import create_app

ORIGIN = {"Origin": "http://testserver"}


@pytest.fixture
def client(tmp_path: Path):
    settings = Settings(_env_file=None, storage_dir=tmp_path / "storage")
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    engine.dispose()
    app = create_app(settings, ollama_probe=lambda: True)
    with TestClient(app) as test_client:
        yield test_client


def _create(client: TestClient, **overrides: str) -> str:
    data = {"title": "Caso de detalle", **overrides}
    response = client.post("/cases", data=data, headers=ORIGIN, follow_redirects=False)
    assert response.status_code == 303
    return response.headers["location"]


def test_unknown_fields_and_synthetic_mark_are_visible(client) -> None:
    location = _create(client)

    detail = client.get(location)

    assert detail.status_code == 200
    assert "Escenario educativo sintético" in detail.text
    assert "No corresponde a una empresa real" in detail.text
    assert detail.text.count("Desconocido") >= 4
    assert "Sin activos registrados" in detail.text


def test_assets_are_listed_when_present(client) -> None:
    location = _create(client, assets="api-gateway\nportal")

    detail = client.get(location)

    assert "api-gateway" in detail.text
    assert "portal" in detail.text
    assert "Sin activos registrados" not in detail.text
