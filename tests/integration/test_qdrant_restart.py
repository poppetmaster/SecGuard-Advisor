"""Persistencia del índice tras reabrir el cliente (reinicio)."""

from __future__ import annotations

from pathlib import Path

from qdrant_client import QdrantClient
from tests.fixtures.corpus import NullEmbedder, seed_document

from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.retrieval.collections import public_scope
from secguard_advisor.retrieval.index import QdrantIndex

INSTANCE = "test-local"


def test_index_survives_client_restart(tmp_path: Path) -> None:
    path = tmp_path / "qdrant"
    settings = Settings(
        _env_file=None,
        storage_dir=tmp_path / "storage",
        instance_id=INSTANCE,
        embedding_dim=NullEmbedder.dimension,
    )
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    embedder = NullEmbedder()

    first = QdrantClient(path=str(path))
    index = QdrantIndex(url="http://127.0.0.1:6333", instance_id=INSTANCE, client=first)
    seeded = seed_document(
        factory, texts=["uno", "dos"], source_id="sample", index=index, embedder=embedder
    )
    index.close()

    second = QdrantClient(path=str(path))
    reopened = QdrantIndex(url="http://127.0.0.1:6333", instance_id=INSTANCE, client=second)
    try:
        assert reopened.count(public_scope(), embedder.model, embedder.dimension) == len(
            seeded.chunk_ids
        )
        hits = reopened.query(
            public_scope(),
            embedder.model,
            embedder.dimension,
            [0.0, 0.0, 0.0, 1.0],
            top_k=10,
        )
        assert {hit.chunk_id for hit in hits} == set(seeded.chunk_ids)
    finally:
        reopened.close()
        engine.dispose()
