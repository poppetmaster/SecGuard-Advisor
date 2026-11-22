"""Reconstrucción inicial e idempotencia en Qdrant."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from qdrant_client import QdrantClient
from tests.fixtures.corpus import NullEmbedder, create_case, seed_document

from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.retrieval.collections import public_scope
from secguard_advisor.retrieval.index import QdrantIndex
from secguard_advisor.retrieval.rebuild import rebuild
from secguard_advisor.retrieval.status import reports_dir

INSTANCE = "test-local"
MODEL = NullEmbedder.model
DIM = NullEmbedder.dimension


@pytest.fixture()
def environment(tmp_path: Path):
    settings = Settings(
        _env_file=None,
        storage_dir=tmp_path / "storage",
        instance_id=INSTANCE,
        embedding_dim=DIM,
    )
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    client = QdrantClient(path=str(tmp_path / "qdrant"))
    index = QdrantIndex(url="http://127.0.0.1:6333", instance_id=INSTANCE, client=client)
    with factory() as session:
        case_id = create_case(session, "Caso A")
        session.commit()
    yield settings, factory, index, case_id
    index.close()
    engine.dispose()


def test_initial_rebuild_validates_and_publishes_alias(environment) -> None:
    settings, factory, index, case_id = environment
    seeded = seed_document(
        factory,
        texts=["control de acceso", "cifrado en reposo"],
        source_id="sample",
        title="Documento público",
    )
    seed_document(
        factory,
        texts=["evidencia privada del caso"],
        case_id=case_id,
        title="Evidencia A",
    )

    report = rebuild(factory, settings, embedder=NullEmbedder(), index=index)

    assert report["status"] == "completed"
    assert {item["scope"] for item in report["scopes"]} == {"public", "case"}
    public = next(item for item in report["scopes"] if item["scope"] == "public")
    assert public["expected_chunks"] == len(seeded.chunk_ids)
    assert public["missing_chunks"] == 0
    assert public["extra_chunks"] == 0

    collection = index.active_collection(public_scope(), MODEL, DIM)
    assert collection is not None
    assert index.count(public_scope(), MODEL, DIM) == len(seeded.chunk_ids)

    latest = json.loads((reports_dir(settings.storage_dir, INSTANCE) / "latest.json").read_text())
    assert latest["status"] == "completed"


def test_rebuild_is_idempotent_and_creates_a_new_generation(environment) -> None:
    settings, factory, index, _ = environment
    seeded = seed_document(factory, texts=["uno", "dos"], source_id="sample")

    first = rebuild(factory, settings, embedder=NullEmbedder(), index=index)
    first_collection = index.active_collection(public_scope(), MODEL, DIM)
    second = rebuild(factory, settings, embedder=NullEmbedder(), index=index)
    second_collection = index.active_collection(public_scope(), MODEL, DIM)

    assert first["status"] == second["status"] == "completed"
    assert first_collection != second_collection
    assert index.count(public_scope(), MODEL, DIM) == len(seeded.chunk_ids)
