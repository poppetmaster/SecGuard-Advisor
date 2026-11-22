"""Recuperación de reconstrucciones fallidas y conservación del alias."""

from __future__ import annotations

from pathlib import Path

import pytest
from qdrant_client import QdrantClient
from tests.fixtures.corpus import NullEmbedder, seed_document

from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.retrieval.collections import public_scope
from secguard_advisor.retrieval.index import QdrantIndex
from secguard_advisor.retrieval.rebuild import rebuild

INSTANCE = "test-local"
MODEL = NullEmbedder.model
DIM = NullEmbedder.dimension


class FailingEmbedder(NullEmbedder):
    def embed_one(self, *_args, **_kwargs):
        raise RuntimeError("fallo simulado")


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
    yield settings, factory, index
    index.close()
    engine.dispose()


def test_failed_rebuild_then_retry_succeeds(environment) -> None:
    settings, factory, index = environment
    seed_document(factory, texts=["uno"], source_id="sample")

    failed = rebuild(factory, settings, embedder=FailingEmbedder(), index=index)
    assert failed["status"] == "failed"
    assert index.active_collection(public_scope(), MODEL, DIM) is None

    retried = rebuild(factory, settings, embedder=NullEmbedder(), index=index)
    assert retried["status"] == "completed"
    assert index.active_collection(public_scope(), MODEL, DIM) is not None


def test_failed_rebuild_keeps_previous_alias(environment) -> None:
    settings, factory, index = environment
    seed_document(factory, texts=["uno"], source_id="sample")
    rebuild(factory, settings, embedder=NullEmbedder(), index=index)
    previous = index.active_collection(public_scope(), MODEL, DIM)

    failed = rebuild(factory, settings, embedder=FailingEmbedder(), index=index)

    assert failed["status"] == "failed"
    assert index.active_collection(public_scope(), MODEL, DIM) == previous
