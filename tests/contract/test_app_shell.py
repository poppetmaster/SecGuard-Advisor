"""Pruebas de contrato de la fábrica de aplicación."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url
from secguard_advisor.web.app import create_app


def _prepare_database(settings: Settings) -> None:
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    engine.dispose()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, storage_dir=tmp_path / "storage")


@pytest.fixture
def client(settings: Settings):
    _prepare_database(settings)
    app = create_app(settings, ollama_probe=lambda: True)
    with TestClient(app) as test_client:
        yield test_client


def test_health_reports_database_and_ollama(client) -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "ok",
        "ollama": "ok",
    }


def test_health_reports_ollama_unavailable(settings: Settings) -> None:
    _prepare_database(settings)
    app = create_app(settings, ollama_probe=lambda: False)

    with TestClient(app) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["ollama"] == "unavailable"


def test_unknown_route_returns_not_found(client) -> None:
    response = client.get("/no-existe")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_cross_origin_post_is_rejected(client) -> None:
    response = client.post("/no-existe", headers={"Origin": "http://evil.example"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden_origin"


def test_same_origin_post_reaches_routing(client) -> None:
    response = client.post("/no-existe", headers={"Origin": "http://testserver"})

    assert response.status_code == 404


def test_static_resources_are_served_locally(client) -> None:
    response = client.get("/static/css/app.css")

    assert response.status_code == 200
    assert "text/css" in response.headers["content-type"]
