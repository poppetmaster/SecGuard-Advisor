"""Contrato de errores de índice en rutas y en el turno conversacional."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from tests.fixtures.fakes import FakeEmbedder, FakeTokenCounter

from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import Case, Run
from secguard_advisor.retrieval.errors import (
    CaseIndexUnavailable,
    PublicIndexUnavailable,
    QdrantUnavailable,
)
from secguard_advisor.web.app import create_app

ORIGIN = {"Origin": "http://testserver"}


class RaisingIndex:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def query(self, *_args, **_kwargs):
        raise self.error

    def upsert(self, *_args, **_kwargs) -> None:
        return None

    def delete_version(self, *_args, **_kwargs) -> None:
        return None


class BombGenerator:
    """Falla si el turno intenta generar una respuesta documental."""

    model = "fake-generator"
    digest = "digest-fake"

    def decide(self, **_kwargs):
        raise AssertionError("el turno no debe decidir tras un fallo de índice")

    def generate(self, **_kwargs):
        raise AssertionError("el turno no debe generar tras un fallo de índice")


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        storage_dir=tmp_path / "storage",
        generation_queue_timeout_seconds=0.2,
    )


def _context(tmp_path: Path):
    settings = _settings(tmp_path)
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        case = Case(title="Caso con fallo de índice", synthetic_notice="Escenario educativo")
        session.add(case)
        session.commit()
        case_id = case.id
    return settings, engine, factory, case_id


@pytest.mark.parametrize(
    ("error", "status", "code", "message"),
    [
        (
            QdrantUnavailable("Qdrant no responde."),
            503,
            "qdrant_unavailable",
            "El índice documental no está disponible.",
        ),
        (
            PublicIndexUnavailable("Falta el alias público."),
            503,
            "public_index_unavailable",
            "El índice público no está disponible.",
        ),
        (
            CaseIndexUnavailable("Falta el alias del caso."),
            503,
            "case_index_unavailable",
            "El índice del caso no está disponible.",
        ),
    ],
)
def test_index_failure_stops_the_turn_without_generation(
    tmp_path: Path, error, status, code, message
) -> None:
    settings, engine, factory, case_id = _context(tmp_path)
    app = create_app(
        settings,
        ollama_probe=lambda: True,
        embedder_factory=lambda: FakeEmbedder(),
        index_factory=lambda: RaisingIndex(error),
        llm_factory=lambda: BombGenerator(),
        token_counter=FakeTokenCounter(),
    )
    try:
        with TestClient(app) as client:
            response = client.post(
                f"/cases/{case_id}/chat/messages",
                data={"question": "¿Qué controles aplicar?"},
                headers=ORIGIN,
            )
        assert response.status_code == status
        assert message in response.text

        with factory() as session:
            run = session.scalar(select(Run))
            assert run is not None
            assert run.error_code == code
            assert run.status == "failed"
            assert run.answer_message_id is None
            assert run.question_message_id is not None
    finally:
        engine.dispose()
