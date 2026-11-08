"""Ingesta del corpus público en SQLite y Chroma."""

import sys

from sqlalchemy.exc import OperationalError

from secguard_advisor.config import get_settings
from secguard_advisor.corpus.ingest import ingest_public_corpus
from secguard_advisor.db.engine import create_engine_for_settings, create_session_factory
from secguard_advisor.documents.embedding import OllamaEmbeddingClient
from secguard_advisor.retrieval.index import ChromaIndex


def main() -> int:
    settings = get_settings()
    settings.ensure_directories()
    engine = create_engine_for_settings(settings)
    factory = create_session_factory(engine)
    embedder = OllamaEmbeddingClient(
        base_url=settings.ollama_base_url,
        model=settings.ollama_embedding_model,
        dimension=settings.embedding_dim,
        context_tokens=settings.embedding_context_tokens,
    )
    index = ChromaIndex(settings.chroma_dir)
    try:
        outcomes = ingest_public_corpus(
            factory,
            settings,
            embedder=embedder,
            index=index,
        )
    except OperationalError:
        print(
            "error: la base no tiene el esquema. Ejecutá `uv run alembic upgrade head`.",
            file=sys.stderr,
        )
        return 2
    finally:
        embedder.close()
        engine.dispose()

    failed = 0
    for outcome in outcomes:
        print(
            f"{outcome.status}: document={outcome.document_id} "
            f"version={outcome.version_id} chunks={outcome.chunks} "
            f"{outcome.message}"
        )
        if outcome.status == "failed":
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
