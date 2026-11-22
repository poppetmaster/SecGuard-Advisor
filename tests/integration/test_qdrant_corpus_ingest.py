"""Integración de la ingesta del corpus público en Qdrant."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from qdrant_client import QdrantClient
from sqlalchemy import select
from tests.fixtures.corpus import NullEmbedder

from secguard_advisor.config import Settings
from secguard_advisor.corpus.ingest import ingest_public_corpus_locked
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import Document
from secguard_advisor.retrieval import instance
from secguard_advisor.retrieval.collections import public_scope
from secguard_advisor.retrieval.index import QdrantIndex

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "files"
INSTANCE = "test-local"


def _tiny_corpus(tmp_path: Path) -> Path:
    corpus = tmp_path / "corpus"
    originals = corpus / "originals"
    originals.mkdir(parents=True)
    original = originals / "sample.pdf"
    original.write_bytes((FIXTURES / "sample.pdf").read_bytes())
    manifest = {
        "sources": [
            {
                "id": "sample",
                "title": "Documento ficticio",
                "status": "verified",
                "sha256": hashlib.sha256(original.read_bytes()).hexdigest(),
                "version_label": "1.0",
                "retrieved_at": "2026-11-22",
                "license": "ficticio",
            }
        ]
    }
    (corpus / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return corpus


@pytest.fixture()
def environment(tmp_path: Path):
    settings = Settings(
        _env_file=None,
        storage_dir=tmp_path / "storage",
        corpus_dir=_tiny_corpus(tmp_path),
        instance_id=INSTANCE,
        embedding_dim=4,
    )
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    client = QdrantClient(path=str(tmp_path / "qdrant"))
    index = QdrantIndex(url="http://127.0.0.1:6333", instance_id=INSTANCE, client=client)
    embedder = NullEmbedder()
    yield settings, factory, index, embedder
    index.close()
    engine.dispose()


def test_public_corpus_ingests_into_qdrant(environment) -> None:
    settings, factory, index, embedder = environment

    outcomes = ingest_public_corpus_locked(factory, settings, embedder=embedder, index=index)

    assert [outcome.status for outcome in outcomes] == ["created"]
    assert index.count(public_scope(), embedder.model, embedder.dimension) > 0
    with factory() as session:
        document = session.scalar(select(Document).where(Document.source_id == "sample"))
        assert document is not None
        assert document.origin == "public_corpus"
        assert document.case_id is None


def test_ingestion_is_rejected_while_rebuild_holds_the_lock(environment) -> None:
    settings, factory, index, embedder = environment

    with (
        instance.acquire_instance_lock(settings.storage_dir, INSTANCE, "rebuild"),
        pytest.raises(instance.InstanceLockBusy) as error,
        ingest_public_corpus_locked(factory, settings, embedder=embedder, index=index),
    ):
        pass

    assert instance.lock_conflict_code(error.value.owner) == "reconstruction_in_progress"
