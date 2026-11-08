"""Utilidades para pruebas de integración con el corpus real."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from secguard_advisor.config import Settings
from secguard_advisor.corpus.ingest import ingest_public_corpus
from secguard_advisor.db.models import Document, DocumentChunk, DocumentVersion
from secguard_advisor.documents.embedding import OllamaEmbeddingClient
from secguard_advisor.retrieval.index import ChromaIndex


def require_corpus(settings: Settings, source_id: str = "csf2") -> None:
    original = settings.corpus_dir / "originals" / f"{source_id}.pdf"
    if not original.exists():
        pytest.skip(f"Falta {original}; ejecutá `make corpus` para las pruebas de integración.")


def real_embedder(settings: Settings) -> OllamaEmbeddingClient:
    return OllamaEmbeddingClient(
        base_url=settings.ollama_base_url,
        model=settings.ollama_embedding_model,
        dimension=settings.embedding_dim,
        context_tokens=settings.embedding_context_tokens,
    )


def ingest_one_public_source(
    settings: Settings,
    factory: sessionmaker[Session],
    *,
    source_id: str = "csf2",
) -> str:
    """Ingesta una fuente oficial verificada con embeddings reales."""
    require_corpus(settings, source_id)
    embedder = real_embedder(settings)
    index = ChromaIndex(settings.chroma_dir)
    try:
        outcomes = ingest_public_corpus(factory, settings, embedder=embedder, index=index)
    finally:
        embedder.close()
    created = [outcome for outcome in outcomes if outcome.document_id]
    if not created:
        pytest.skip("El corpus no está verificado; ejecutá `make corpus`.")
    with factory() as session:
        document = session.scalar(select(Document).where(Document.source_id == source_id))
        assert document is not None
        return document.id


def first_chunk_text(
    factory: sessionmaker[Session], document_id: str
) -> tuple[str, str, int | None]:
    with factory() as session:
        document = session.get(Document, document_id)
        version = session.get(DocumentVersion, document.current_version_id)
        chunk = session.scalar(
            select(DocumentChunk)
            .where(DocumentChunk.version_id == version.id)
            .order_by(DocumentChunk.chunk_index)
        )
        assert chunk is not None
        return chunk.text, chunk.id, chunk.page_start
