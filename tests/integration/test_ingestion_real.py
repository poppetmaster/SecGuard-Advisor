"""Integración real de ingesta con EmbeddingGemma y Chroma."""

from pathlib import Path

import pytest
from sqlalchemy import select

from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import Case, DocumentChunk
from secguard_advisor.documents.embedding import OllamaEmbeddingClient
from secguard_advisor.documents.service import ingest_document
from secguard_advisor.documents.validation import validate_bytes
from secguard_advisor.retrieval.collections import case_scope
from secguard_advisor.retrieval.index import ChromaIndex

pytestmark = pytest.mark.integration


def test_real_ingestion_measures_tokens_and_indexes(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, storage_dir=tmp_path / "storage")
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)

    with factory() as session:
        case = Case(title="Caso real", synthetic_notice="Escenario educativo")
        session.add(case)
        session.commit()
        case_id = case.id

    data = (
        "# Sección de prueba\n" + "Contenido sobre gestión de riesgos y controles. " * 200
    ).encode("utf-8")
    upload = validate_bytes("largo.md", data, settings.max_upload_bytes)

    embedder = OllamaEmbeddingClient(
        base_url=settings.ollama_base_url,
        model=settings.ollama_embedding_model,
        dimension=settings.embedding_dim,
        context_tokens=settings.embedding_context_tokens,
    )
    index = ChromaIndex(settings.chroma_dir)

    try:
        outcome = ingest_document(
            factory,
            settings,
            scope_key=f"case:{case_id}",
            case_id=case_id,
            origin="case_evidence",
            source_id=None,
            title="Documento real",
            upload=upload,
            embedder=embedder,
            index=index,
        )

        assert outcome.status == "created"
        assert outcome.chunks > 0

        with factory() as session:
            chunks = list(
                session.scalars(
                    select(DocumentChunk).where(DocumentChunk.version_id == outcome.version_id)
                )
            )
        assert chunks
        assert all(chunk.token_count <= 2048 for chunk in chunks)
        assert max(chunk.token_count for chunk in chunks) > 0
        assert all(
            chunk.token_count_source == "ollama_prompt_eval_count_single" for chunk in chunks
        )
        assert all(chunk.index_status == "indexed" for chunk in chunks)

        assert index.count(
            case_scope(case_id),
            settings.ollama_embedding_model,
            settings.embedding_dim,
        ) == len(chunks)

        query = embedder.embed_one("¿De qué trata el documento?", kind="query")
        hits = index.query(
            case_scope(case_id),
            settings.ollama_embedding_model,
            settings.embedding_dim,
            query.vector,
            top_k=3,
        )
        assert hits
    finally:
        embedder.close()
        engine.dispose()
