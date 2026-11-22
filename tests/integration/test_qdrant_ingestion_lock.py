"""El lock de ingesta cubre también la confirmación de disponibilidad."""

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
from secguard_advisor.retrieval import instance
from secguard_advisor.retrieval.collections import case_scope
from secguard_advisor.retrieval.index import QdrantIndex
from secguard_advisor.retrieval.rebuild import rebuild
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


def _ingest(factory, settings, case_id, index, filename: str, title: str):
    upload = validate_bytes(filename, (FIXTURES / filename).read_bytes(), settings.max_upload_bytes)
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


def test_rebuild_cannot_enter_before_availability_commit(environment, monkeypatch) -> None:
    settings, factory, index, case_id = environment
    first = _ingest(factory, settings, case_id, index, "sample.pdf", "Primero")
    assert first.status == "created"

    original = service._mark_available
    observed: dict[str, object] = {}

    def mark_with_probe(*args, **kwargs):
        observed["lock"] = instance.inspect_lock(settings.storage_dir, INSTANCE)
        try:
            rebuild(factory, settings, embedder=NullEmbedder(), index=index)
        except instance.InstanceLockBusy as exc:
            observed["conflict"] = instance.lock_conflict_code(exc.owner)
        return original(*args, **kwargs)

    monkeypatch.setattr(service, "_mark_available", mark_with_probe)
    second = _ingest(factory, settings, case_id, index, "sample.md", "Segundo")

    assert second.status == "created"
    owner = observed["lock"]
    assert owner is not None and owner.operation == "ingestion"
    assert observed["conflict"] == "ingestion_in_progress"
    assert instance.inspect_lock(settings.storage_dir, INSTANCE) is None

    report = rebuild(factory, settings, embedder=NullEmbedder(), index=index)
    assert report["status"] == "completed"
    with factory() as session:
        result = search_documents(
            session,
            scope=CaseScope(case_id=case_id),
            query="consulta",
            embedder=NullEmbedder(),
            index=index,
            top_k=10,
            min_score=0.0,
        )
    assert {first.version_id, second.version_id} <= {hit.version_id for hit in result.hits}


def test_lock_is_released_after_commit_failure_and_retry_converges(
    environment, monkeypatch
) -> None:
    settings, factory, index, case_id = environment
    original = service._mark_available
    calls = {"count": 0}

    def failing_once(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("fallo de commit SQLite")
        return original(*args, **kwargs)

    monkeypatch.setattr(service, "_mark_available", failing_once)
    failed = _ingest(factory, settings, case_id, index, "sample.pdf", "Primero")

    assert failed.status == "failed"
    assert instance.inspect_lock(settings.storage_dir, INSTANCE) is None
    with factory() as session:
        assert session.get(DocumentVersion, failed.version_id).status == "failed"
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
    assert instance.inspect_lock(settings.storage_dir, INSTANCE) is None
    assert index.count(case_scope(case_id), MODEL, DIM) == retried.chunks
