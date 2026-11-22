"""Primer documento, documentos posteriores y convergencia sin atomicidad."""

from __future__ import annotations

from pathlib import Path

import pytest
from qdrant_client import QdrantClient
from sqlalchemy import select
from tests.fixtures.corpus import NullEmbedder, create_case

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import DocumentVersion
from secguard_advisor.documents import service
from secguard_advisor.documents.service import ingest_document, retry_ingestion
from secguard_advisor.documents.validation import validate_bytes
from secguard_advisor.retrieval.collections import case_scope
from secguard_advisor.retrieval.index import QdrantIndex
from secguard_advisor.retrieval.search import search_documents

INSTANCE = "test-local"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "files"
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
    yield settings, factory, index, case_id
    index.close()
    engine.dispose()


def _ingest(factory, settings, case_id, index, title="Evidencia"):
    upload = validate_bytes(
        "sample.pdf", (FIXTURES / "sample.pdf").read_bytes(), settings.max_upload_bytes
    )
    return ingest_document(
        factory,
        settings,
        scope_key=f"case:{case_id}",
        case_id=case_id,
        origin="case_evidence",
        source_id=None,
        title=title,
        upload=upload,
        embedder=NullEmbedder(),
        index=index,
        declared_version=None,
        retrieved_at=None,
        license=None,
        store_original_file=True,
    )


def _search(factory, index, case_id):
    with factory() as session:
        return search_documents(
            session,
            scope=CaseScope(case_id=case_id),
            query="consulta",
            embedder=NullEmbedder(),
            index=index,
            top_k=10,
            min_score=0.0,
        )


def test_first_document_is_available_and_searchable(environment) -> None:
    settings, factory, index, case_id = environment

    outcome = _ingest(factory, settings, case_id, index)

    assert outcome.status == "created"
    collection = index.active_collection(case_scope(case_id), MODEL, DIM)
    assert collection is not None
    result = _search(factory, index, case_id)
    assert result.status == "ok"
    assert outcome.version_id in {hit.version_id for hit in result.hits}


def test_second_document_reuses_the_alias(environment) -> None:
    settings, factory, index, case_id = environment

    first = _ingest(factory, settings, case_id, index, title="Primero")
    collection = index.active_collection(case_scope(case_id), MODEL, DIM)
    second = _ingest(factory, settings, case_id, index, title="Segundo")

    assert index.active_collection(case_scope(case_id), MODEL, DIM) == collection
    result = _search(factory, index, case_id)
    versions = {hit.version_id for hit in result.hits}
    assert {first.version_id, second.version_id} <= versions


def test_sqlite_commit_failure_converges_without_duplicates(environment, monkeypatch) -> None:
    settings, factory, index, case_id = environment

    original = service._mark_available
    calls = {"count": 0}

    def failing_mark(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("fallo de commit SQLite")
        return original(*args, **kwargs)

    monkeypatch.setattr(service, "_mark_available", failing_mark)
    failed = _ingest(factory, settings, case_id, index, title="Primero")
    assert failed.status == "failed"
    with factory() as session:
        version = session.get(DocumentVersion, failed.version_id)
        assert version.status == "failed"

    result = _search(factory, index, case_id)
    assert failed.version_id not in {hit.version_id for hit in result.hits}

    with factory() as session:
        document_id = session.scalar(
            select(DocumentVersion.document_id).where(DocumentVersion.id == failed.version_id)
        )
    retried = retry_ingestion(
        factory,
        settings,
        scope=CaseScope(case_id=case_id),
        document_id=document_id,
        embedder=NullEmbedder(),
        index=index,
    )
    assert retried.status == "created"

    total = index.count(case_scope(case_id), MODEL, DIM)
    assert total == retried.chunks
    result = _search(factory, index, case_id)
    assert retried.version_id in {hit.version_id for hit in result.hits}
