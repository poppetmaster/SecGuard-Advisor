"""Disponibilidad de Qdrant y configuración de instancia incompatible."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient
from tests.fixtures.fakes import FakeEmbedder, FakeTokenCounter

from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import Case
from secguard_advisor.retrieval import instance
from secguard_advisor.retrieval.collections import public_scope
from secguard_advisor.retrieval.errors import IndexConfigurationError, QdrantUnavailable
from secguard_advisor.retrieval.index import QdrantIndex
from secguard_advisor.web.app import create_app

INSTANCE = "test-local"


class BombGenerator:
    model = "fake-generator"
    digest = "digest-fake"

    def decide(self, **_kwargs):
        raise AssertionError("no debe decidir")

    def generate(self, **_kwargs):
        raise AssertionError("no debe generar")


def test_unreachable_server_raises_qdrant_unavailable() -> None:
    index = QdrantIndex(url="http://127.0.0.1:1", instance_id=INSTANCE, timeout=0.5)

    with pytest.raises(QdrantUnavailable):
        index.query(public_scope(), "embeddinggemma", 768, [0.0] * 768)


def test_marker_mismatch_raises_configuration_error(tmp_path: Path) -> None:
    original = tmp_path / "original"
    original.mkdir()
    instance.ensure_marker(original, INSTANCE, namespace_present=False)

    copy = tmp_path / "copy"
    (copy / "qdrant-control" / "instances").mkdir(parents=True)
    (copy / "qdrant-control" / "instances" / f"{INSTANCE}.json").write_text(
        instance.marker_path(original, INSTANCE).read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    client = QdrantClient(path=str(tmp_path / "qdrant"))
    index = QdrantIndex(
        url="http://127.0.0.1:6333",
        instance_id=INSTANCE,
        client=client,
        storage_dir=copy,
    )
    try:
        with pytest.raises(IndexConfigurationError):
            index.query(public_scope(), "embeddinggemma", 4, [0.0, 0.0, 0.0, 1.0])
    finally:
        index.close()


def test_route_returns_503_when_qdrant_is_down(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        storage_dir=tmp_path / "storage",
        generation_queue_timeout_seconds=0.2,
    )
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        case = Case(title="Caso sin Qdrant", synthetic_notice="Escenario educativo")
        session.add(case)
        session.commit()
        case_id = case.id
    index = QdrantIndex(url="http://127.0.0.1:1", instance_id=INSTANCE, timeout=0.5)
    app = create_app(
        settings,
        ollama_probe=lambda: True,
        embedder_factory=lambda: FakeEmbedder(),
        index_factory=lambda: index,
        llm_factory=lambda: BombGenerator(),
        token_counter=FakeTokenCounter(),
        qdrant_probe=lambda: False,
    )
    try:
        with TestClient(app) as client:
            response = client.post(
                f"/cases/{case_id}/chat/messages",
                data={"question": "¿qué controles aplicar?"},
                headers={"Origin": "http://testserver"},
            )
        assert response.status_code == 503
        assert "El índice documental no está disponible." in response.text
    finally:
        index.close()
        engine.dispose()
