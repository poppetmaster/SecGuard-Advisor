"""Integración de reimportación, versiones y citas históricas."""

from pathlib import Path

import pytest
from sqlalchemy import select

from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import Case, Document, DocumentChunk, DocumentVersion
from secguard_advisor.documents.embedding import OllamaEmbeddingClient
from secguard_advisor.documents.service import ingest_document
from secguard_advisor.documents.validation import validate_bytes
from secguard_advisor.retrieval.collections import case_scope
from secguard_advisor.retrieval.index import ChromaIndex

pytestmark = pytest.mark.integration


def test_reimport_and_new_version_keep_history(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, storage_dir=tmp_path / "storage")
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)

    with factory() as session:
        case = Case(title="Caso versiones", synthetic_notice="Escenario educativo")
        session.add(case)
        session.commit()
        case_id = case.id

    embedder = OllamaEmbeddingClient(
        base_url=settings.ollama_base_url,
        model=settings.ollama_embedding_model,
        dimension=settings.embedding_dim,
        context_tokens=settings.embedding_context_tokens,
    )
    index = ChromaIndex(settings.chroma_dir)

    def ingest(content: bytes):
        return ingest_document(
            factory,
            settings,
            scope_key=f"case:{case_id}",
            case_id=case_id,
            origin="case_evidence",
            source_id=None,
            title="Documento versionado",
            upload=validate_bytes("doc.md", content, settings.max_upload_bytes),
            embedder=embedder,
            index=index,
        )

    try:
        first = ingest(b"# Uno\nContenido de la primera version.")
        duplicate = ingest(b"# Uno\nContenido de la primera version.")
        second = ingest(b"# Dos\nContenido de la segunda version.")

        assert first.status == "created"
        assert duplicate.status == "duplicate"
        assert second.status == "created"
        assert second.version_number == 2

        with factory() as session:
            document = session.get(Document, first.document_id)
            old = session.get(DocumentVersion, first.version_id)
            new = session.get(DocumentVersion, second.version_id)
            old_chunks = list(
                session.scalars(select(DocumentChunk).where(DocumentChunk.version_id == old.id))
            )
            assert old.status == "superseded"
            assert new.status == "available"
            assert document.current_version_id == new.id
            assert old_chunks
            assert session.get(DocumentChunk, old_chunks[0].id) is not None

        assert (
            index.count(
                case_scope(case_id),
                settings.ollama_embedding_model,
                settings.embedding_dim,
            )
            == len(old_chunks) + second.chunks
        )
    finally:
        embedder.close()
        engine.dispose()
