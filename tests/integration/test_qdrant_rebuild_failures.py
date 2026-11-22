"""Fallas, parciales, reintento y discrepancias de la reconstrucción."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from sqlalchemy import select
from tests.fixtures.corpus import NullEmbedder, seed_document

from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import DocumentChunk
from secguard_advisor.retrieval import instance
from secguard_advisor.retrieval.collections import public_scope
from secguard_advisor.retrieval.index import QdrantIndex, point_id
from secguard_advisor.retrieval.rebuild import rebuild
from secguard_advisor.retrieval.status import reports_dir

INSTANCE = "test-local"
MODEL = NullEmbedder.model
DIM = NullEmbedder.dimension


class FailingEmbedder(NullEmbedder):
    def embed_one(self, text: str, *, kind: str = "document", title=None):
        raise RuntimeError("fallo simulado de embeddings")


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


def _latest(settings: Settings) -> dict:
    return json.loads((reports_dir(settings.storage_dir, INSTANCE) / "latest.json").read_text())


def test_rebuild_is_rejected_while_ingestion_holds_the_lock(environment) -> None:
    settings, factory, index = environment
    seed_document(factory, texts=["uno"], source_id="sample")

    with (
        instance.acquire_instance_lock(settings.storage_dir, INSTANCE, "ingestion"),
        pytest.raises(instance.InstanceLockBusy) as error,
        rebuild(factory, settings, embedder=NullEmbedder(), index=index),
    ):
        pass

    assert instance.lock_conflict_code(error.value.owner) == "ingestion_in_progress"


def test_embedding_failure_leaves_no_alias(environment) -> None:
    settings, factory, index = environment
    seed_document(factory, texts=["uno"], source_id="sample")

    report = rebuild(factory, settings, embedder=FailingEmbedder(), index=index)

    assert report["status"] == "failed"
    assert index.active_collection(public_scope(), MODEL, DIM) is None
    assert _latest(settings)["status"] == "failed"


def test_skipped_chunk_keeps_previous_alias(environment) -> None:
    settings, factory, index = environment
    seed_document(factory, texts=["uno"], source_id="sample")
    rebuild(factory, settings, embedder=NullEmbedder(), index=index)
    previous = index.active_collection(public_scope(), MODEL, DIM)

    with factory() as session:
        chunk = session.scalars(select(DocumentChunk)).first()
        chunk.embedding_dim = DIM + 4
        session.commit()

    report = rebuild(factory, settings, embedder=NullEmbedder(), index=index)

    assert report["status"] == "partial"
    assert report["scopes"][0]["skipped_chunks"] == 1
    assert index.active_collection(public_scope(), MODEL, DIM) == previous


def test_orphan_point_is_reported_and_alias_unchanged(environment) -> None:
    settings, factory, index = environment
    seed_document(factory, texts=["uno"], source_id="sample")
    rebuild(factory, settings, embedder=NullEmbedder(), index=index)
    previous = index.active_collection(public_scope(), MODEL, DIM)
    orphan = "f" * 32
    index.client.upsert(
        collection_name=previous,
        points=[
            PointStruct(
                id=point_id(orphan),
                vector=[0.0, 0.0, 0.0, 1.0],
                payload={"chunk_id": orphan, "origin": "public_corpus"},
            )
        ],
    )

    report = rebuild(factory, settings, embedder=NullEmbedder(), index=index)

    assert report["status"] == "partial"
    assert report["scopes"][0]["extra_chunks"] == 1
    assert index.active_collection(public_scope(), MODEL, DIM) == previous


def test_stale_lock_metadata_does_not_block(environment) -> None:
    settings, factory, index = environment
    seed_document(factory, texts=["uno"], source_id="sample")
    lock = instance.lock_path(settings.storage_dir, INSTANCE)
    lock.parent.mkdir(parents=True)
    lock.write_text(
        json.dumps(
            {
                "operation": "rebuild",
                "attempt_id": "viejo",
                "pid": 999999,
                "started_at": "2026-11-22T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    report = rebuild(factory, settings, embedder=NullEmbedder(), index=index)

    assert report["status"] == "completed"
