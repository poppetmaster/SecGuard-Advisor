"""Estado por alcance y no finalización global de la reconstrucción."""

from __future__ import annotations

from pathlib import Path

import pytest
from qdrant_client import QdrantClient
from sqlalchemy import select
from tests.fixtures.corpus import NullEmbedder, create_case, seed_document

from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import Document, DocumentChunk
from secguard_advisor.retrieval.collections import case_scope, public_scope
from secguard_advisor.retrieval.index import QdrantIndex
from secguard_advisor.retrieval.rebuild import rebuild

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
        case_id = create_case(session, "Caso")
        session.commit()
    seed_document(factory, texts=["público"], source_id="sample")
    seed_document(factory, texts=["privado"], case_id=case_id)
    yield settings, factory, index, case_id
    index.close()
    engine.dispose()


def _corrupt_public_chunk(factory) -> None:
    with factory() as session:
        public_document = session.scalar(select(Document).where(Document.origin == "public_corpus"))
        chunk = session.scalar(
            select(DocumentChunk).where(
                DocumentChunk.version_id == public_document.current_version_id
            )
        )
        chunk.embedding_dim = DIM + 4
        session.commit()


def test_partial_rebuild_publishes_valid_scope_only(environment) -> None:
    settings, factory, index, case_id = environment
    _corrupt_public_chunk(factory)

    report = rebuild(factory, settings, embedder=NullEmbedder(), index=index)

    assert report["status"] == "partial"
    scopes = {item["scope"]: item for item in report["scopes"]}
    assert scopes["public"]["status"] == "partial"
    assert scopes["public"]["skipped_chunks"] == 1
    assert scopes["case"]["status"] == "completed"
    assert index.active_collection(public_scope(), MODEL, DIM) is None
    assert index.active_collection(case_scope(case_id), MODEL, DIM) is not None


def test_retry_after_fixing_scope_completes_both(environment) -> None:
    settings, factory, index, case_id = environment
    _corrupt_public_chunk(factory)
    rebuild(factory, settings, embedder=NullEmbedder(), index=index)

    with factory() as session:
        chunk = session.scalar(select(DocumentChunk).where(DocumentChunk.embedding_dim != DIM))
        chunk.embedding_dim = DIM
        session.commit()

    report = rebuild(factory, settings, embedder=NullEmbedder(), index=index)

    assert report["status"] == "completed"
    assert index.active_collection(public_scope(), MODEL, DIM) is not None
    assert index.active_collection(case_scope(case_id), MODEL, DIM) is not None
