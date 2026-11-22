"""Ciclo del primer documento: validación, fallo y reintento convergente."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from tests.fixtures.corpus import NullEmbedder, create_case

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import DocumentVersion
from secguard_advisor.documents import service
from secguard_advisor.documents.embedding import EmbeddingError
from secguard_advisor.documents.service import ingest_document, retry_ingestion
from secguard_advisor.documents.validation import validate_bytes
from secguard_advisor.retrieval.index import IndexedChunk

INSTANCE = "test-local"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "files"
MODEL = NullEmbedder.model
DIM = NullEmbedder.dimension


class FirstDocIndex:
    """Índice guionizado con la interfaz de generación/alias."""

    def __init__(self) -> None:
        self.active: dict[tuple[str, str | None], str] = {}
        self.created: list[str] = []
        self.upserted: dict[str, set[str]] = {}
        self.activated: list[str] = []
        self.fail_upsert = False
        self.incomplete_validation = False
        self.upsert_calls = 0

    def _key(self, scope):
        return (scope.kind, scope.case_id)

    def active_collection(self, scope, _model, _dimension):
        return self.active.get(self._key(scope))

    def create_generation(self, scope, _model, _dimension):
        generation = f"g{len(self.created) + 1}"
        name = f"collection-{generation}"
        self.created.append(name)
        return generation, name

    def upsert_to(self, collection: str, chunks: list[IndexedChunk]) -> None:
        self.upsert_calls += 1
        if self.fail_upsert:
            raise RuntimeError("fallo de escritura")
        self.upserted.setdefault(collection, set()).update(c.chunk_id for c in chunks)

    def chunk_ids(self, collection: str) -> set[str]:
        ids = set(self.upserted.get(collection, set()))
        if self.incomplete_validation and ids:
            ids.discard(sorted(ids)[0])
        return ids

    def activate_alias(self, scope, _model, _dimension, collection: str) -> None:
        self.activated.append(collection)
        self.active[self._key(scope)] = collection

    def delete_version(self, *_args, **_kwargs) -> None:
        return None

    def upsert(self, scope, _model, _dimension, chunks: list[IndexedChunk]) -> None:
        self.upsert_calls += 1
        if self.fail_upsert:
            raise RuntimeError("fallo de escritura")
        collection = self.active[self._key(scope)]
        self.upserted.setdefault(collection, set()).update(c.chunk_id for c in chunks)


def _environment(tmp_path: Path):
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
    with factory() as session:
        case_id = create_case(session, "Caso")
        session.commit()
    return settings, factory, case_id


def _ingest(factory, settings, case_id, index, embedder=None):
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
        title="Evidencia",
        upload=upload,
        embedder=embedder or NullEmbedder(),
        index=index,
        declared_version=None,
        retrieved_at=None,
        license=None,
        store_original_file=True,
    )


def test_first_document_validates_before_publishing_alias(tmp_path: Path) -> None:
    settings, factory, case_id = _environment(tmp_path)
    index = FirstDocIndex()

    outcome = _ingest(factory, settings, case_id, index)

    assert outcome.status == "created"
    assert len(index.created) == 1
    assert index.activated == index.created
    assert len(index.upserted[index.created[0]]) == outcome.chunks
    with factory() as session:
        version = session.scalar(select(DocumentVersion))
        assert version is not None
        assert version.status == "available"


def test_first_document_write_failure_does_not_publish_alias(tmp_path: Path) -> None:
    settings, factory, case_id = _environment(tmp_path)
    index = FirstDocIndex()
    index.fail_upsert = True

    outcome = _ingest(factory, settings, case_id, index)

    assert outcome.status == "failed"
    assert index.activated == []
    with factory() as session:
        assert session.scalar(select(DocumentVersion)).status == "failed"


def test_first_document_validation_mismatch_does_not_publish_alias(tmp_path: Path) -> None:
    settings, factory, case_id = _environment(tmp_path)
    index = FirstDocIndex()
    index.incomplete_validation = True

    outcome = _ingest(factory, settings, case_id, index)

    assert outcome.status == "failed"
    assert index.activated == []


def test_embedding_failure_does_not_touch_the_index(tmp_path: Path) -> None:
    class FailingEmbedder(NullEmbedder):
        def embed_one(self, *_args, **_kwargs):
            raise EmbeddingError("fallo de embeddings")

    settings, factory, case_id = _environment(tmp_path)
    index = FirstDocIndex()

    outcome = _ingest(factory, settings, case_id, index, FailingEmbedder())

    assert outcome.status == "failed"
    assert index.created == []
    assert index.upsert_calls == 0


def test_commit_failure_marks_failed_and_retry_converges(tmp_path: Path, monkeypatch) -> None:
    settings, factory, case_id = _environment(tmp_path)
    index = FirstDocIndex()
    original = service._mark_available
    calls = {"count": 0}

    def failing_mark(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("fallo de commit SQLite")
        return original(*args, **kwargs)

    monkeypatch.setattr(service, "_mark_available", failing_mark)
    first = _ingest(factory, settings, case_id, index)
    assert first.status == "failed"
    assert first.version_id

    with factory() as session:
        document_id = session.scalar(select(DocumentVersion.document_id))
    retried = retry_ingestion(
        factory,
        settings,
        scope=CaseScope(case_id=case_id),
        document_id=document_id,
        embedder=NullEmbedder(),
        index=index,
    )

    assert retried.status == "created"
    with factory() as session:
        version = session.get(DocumentVersion, retried.version_id)
        assert version.status == "available"
    assert index.upsert_calls == 2
    assert retried.chunks >= 1
    # La ausencia de duplicados se demuestra con el adaptador real en la prueba
    # de integración: el doble no modela delete_version por payload.
