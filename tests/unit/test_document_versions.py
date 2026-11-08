"""Pruebas de deduplicación, versiones y estados de ingesta."""

from pathlib import Path

import pytest
from sqlalchemy import func, select
from tests.fixtures.fakes import FakeEmbedder, FakeIndex

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import (
    Case,
    Document,
    DocumentChunk,
    DocumentVersion,
    IngestionJob,
)
from secguard_advisor.documents.service import ingest_document, retry_ingestion
from secguard_advisor.documents.validation import validate_bytes

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


@pytest.fixture
def context(tmp_path: Path):
    settings = Settings(_env_file=None, storage_dir=tmp_path / "storage")
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        case = Case(title="Caso", synthetic_notice="Escenario educativo")
        session.add(case)
        session.commit()
        case_id = case.id
    yield settings, factory, case_id
    engine.dispose()


def _upload(filename: str, data: bytes):
    return validate_bytes(filename, data, 10_000_000)


def _ingest(
    settings: Settings,
    factory,
    case_id: str,
    filename: str,
    data: bytes,
    *,
    embedder=None,
    index=None,
):
    return ingest_document(
        factory,
        settings,
        scope_key=f"case:{case_id}",
        case_id=case_id,
        origin="case_evidence",
        source_id=None,
        title="Documento",
        upload=_upload(filename, data),
        embedder=embedder or FakeEmbedder(),
        index=index or FakeIndex(),
    )


def test_new_markdown_becomes_available(context) -> None:
    settings, factory, case_id = context

    outcome = _ingest(settings, factory, case_id, "doc.md", b"# Uno\nContenido uno.")

    assert outcome.status == "created"
    assert outcome.chunks > 0
    with factory() as session:
        version = session.get(DocumentVersion, outcome.version_id)
        document = session.get(Document, outcome.document_id)
        job = session.scalars(
            select(IngestionJob).where(IngestionJob.version_id == version.id)
        ).one()
        chunks = list(
            session.scalars(select(DocumentChunk).where(DocumentChunk.version_id == version.id))
        )
        assert version.status == "available"
        assert document.current_version_id == version.id
        assert job.status == "succeeded"
        assert len(chunks) == outcome.chunks
        assert all(chunk.token_count == 10 for chunk in chunks)
        assert all(chunk.index_status == "indexed" for chunk in chunks)


def test_identical_reimport_is_duplicate(context) -> None:
    settings, factory, case_id = context
    data = b"# Uno\nContenido uno."

    first = _ingest(settings, factory, case_id, "doc.md", data)
    second = _ingest(settings, factory, case_id, "doc.md", data)

    assert first.status == "created"
    assert second.status == "duplicate"
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Document)) == 1
        assert session.scalar(select(func.count()).select_from(DocumentVersion)) == 1


def test_modified_same_filename_creates_version_and_supersedes(context) -> None:
    settings, factory, case_id = context
    first = _ingest(settings, factory, case_id, "doc.md", b"# Uno\nContenido uno.")
    second = _ingest(settings, factory, case_id, "doc.md", b"# Dos\nContenido dos.")

    assert second.status == "created"
    assert second.version_number == 2
    with factory() as session:
        old = session.get(DocumentVersion, first.version_id)
        new = session.get(DocumentVersion, second.version_id)
        document = session.get(Document, first.document_id)
        assert old.status == "superseded"
        assert old.superseded_at is not None
        assert new.status == "available"
        assert document.current_version_id == new.id
        assert (
            session.scalar(
                select(func.count())
                .select_from(DocumentChunk)
                .where(DocumentChunk.version_id == old.id)
            )
            > 0
        )


def test_different_filename_creates_new_document(context) -> None:
    settings, factory, case_id = context

    first = _ingest(settings, factory, case_id, "a.md", b"# A\nContenido A.")
    second = _ingest(settings, factory, case_id, "b.md", b"# B\nContenido B.")

    assert first.document_id != second.document_id
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Document)) == 2


def test_blank_pdf_is_no_usable_text(context) -> None:
    settings, factory, case_id = context

    outcome = _ingest(
        settings,
        factory,
        case_id,
        "blank.pdf",
        (FIXTURES / "blank.pdf").read_bytes(),
    )

    assert outcome.status == "no_usable_text"
    with factory() as session:
        version = session.get(DocumentVersion, outcome.version_id)
        document = session.get(Document, outcome.document_id)
        assert version.status == "no_usable_text"
        assert "texto utilizable" in (version.error_message or "")
        assert document.current_version_id is None


def test_embedding_failure_marks_version_failed(context) -> None:
    settings, factory, case_id = context

    outcome = _ingest(
        settings,
        factory,
        case_id,
        "doc.md",
        b"# Uno\nContenido uno.",
        embedder=FakeEmbedder(fail=True),
    )

    assert outcome.status == "failed"
    with factory() as session:
        version = session.get(DocumentVersion, outcome.version_id)
        document = session.get(Document, outcome.document_id)
        assert version.status == "failed"
        assert document.current_version_id is None


def test_index_failure_marks_version_failed(context) -> None:
    settings, factory, case_id = context

    outcome = _ingest(
        settings,
        factory,
        case_id,
        "doc.md",
        b"# Uno\nContenido uno.",
        index=FakeIndex(fail=True),
    )

    assert outcome.status == "failed"
    with factory() as session:
        version = session.get(DocumentVersion, outcome.version_id)
        assert version.status == "failed"


def test_retry_reuses_failed_version(context) -> None:
    settings, factory, case_id = context
    failed = _ingest(
        settings,
        factory,
        case_id,
        "doc.md",
        b"# Uno\nContenido uno.",
        embedder=FakeEmbedder(fail=True),
    )

    outcome = retry_ingestion(
        factory,
        settings,
        scope=CaseScope(case_id=case_id),
        document_id=failed.document_id,
        embedder=FakeEmbedder(),
        index=FakeIndex(),
    )

    assert outcome.status == "created"
    with factory() as session:
        version = session.get(DocumentVersion, failed.version_id)
        jobs = list(
            session.scalars(select(IngestionJob).where(IngestionJob.version_id == version.id))
        )
        assert version.status == "available"
        assert max(job.attempts for job in jobs) == 2


def test_public_document_has_no_case(context) -> None:
    settings, factory, _case_id = context

    outcome = ingest_document(
        factory,
        settings,
        scope_key="public:csf2",
        case_id=None,
        origin="public_corpus",
        source_id="csf2",
        title="CSF",
        upload=_upload("csf2.pdf", (FIXTURES / "sample.pdf").read_bytes()),
        embedder=FakeEmbedder(),
        index=FakeIndex(),
    )

    assert outcome.status == "created"
    with factory() as session:
        document = session.get(Document, outcome.document_id)
        assert document.case_id is None
        assert document.origin == "public_corpus"
        assert document.source_id == "csf2"
