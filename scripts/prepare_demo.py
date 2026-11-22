"""Prepara la instancia de demostración sin tocar el almacenamiento del usuario.

Requiere que el corpus oficial ya esté descargado (`make corpus`). No descarga en
cada arranque: si faltan originales, informa y sale con error.
"""

from __future__ import annotations

import sys

from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from secguard_advisor.config import get_settings
from secguard_advisor.corpus.ingest import ingest_public_corpus_locked
from secguard_advisor.db.engine import create_engine_for_settings, create_session_factory
from secguard_advisor.db.models import (
    Case,
    Document,
    DocumentChunk,
    Finding,
    SyntheticDataset,
)
from secguard_advisor.documents.embedding import OllamaEmbeddingClient
from secguard_advisor.retrieval.index import QdrantIndex
from secguard_advisor.retrieval.instance import (
    InstanceConfigurationError,
    InstanceLockBusy,
    lock_conflict_code,
)
from secguard_advisor.seed.demo import seed_demo


def main() -> int:
    settings = get_settings()
    settings.ensure_directories()
    manifest = settings.corpus_dir / "manifest.json"
    originals = settings.corpus_dir / "originals"
    if not manifest.exists() or not originals.exists():
        print(
            "faltan el manifiesto o los originales del corpus; ejecutá `make corpus` una vez.",
            file=sys.stderr,
        )
        return 2

    engine = create_engine_for_settings(settings)
    factory = create_session_factory(engine)
    embedder = OllamaEmbeddingClient(
        base_url=settings.ollama_base_url,
        model=settings.ollama_embedding_model,
        dimension=settings.embedding_dim,
        context_tokens=settings.embedding_context_tokens,
    )
    index = QdrantIndex(
        url=settings.qdrant_url,
        instance_id=settings.instance_id,
        timeout=settings.qdrant_timeout_seconds,
    )
    try:
        with factory() as session:
            report = seed_demo(session)
            session.commit()
        outcomes = ingest_public_corpus_locked(
            factory,
            settings,
            embedder=embedder,
            index=index,
        )
    except InstanceConfigurationError:
        print(
            "instance_configuration_invalid: definí SECGUARD_INSTANCE_ID antes de ingestar.",
            file=sys.stderr,
        )
        return 2
    except InstanceLockBusy as exc:
        print(
            f"{lock_conflict_code(exc.owner)}: otra operación mantiene el lock de instancia.",
            file=sys.stderr,
        )
        return 3
    except OperationalError:
        print(
            "la base de demostración no tiene esquema; ejecutá `make demo-prepare`.",
            file=sys.stderr,
        )
        return 2
    finally:
        embedder.close()
        index.close()
        engine.dispose()

    failed = [outcome for outcome in outcomes if outcome.status == "failed"]
    engine = create_engine_for_settings(settings)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            public_documents = session.scalar(
                select(func.count()).select_from(Document).where(Document.origin == "public_corpus")
            )
            chunks = session.scalar(select(func.count()).select_from(DocumentChunk))
            findings = session.scalar(select(func.count()).select_from(Finding))
            dataset = session.scalar(select(SyntheticDataset).order_by(SyntheticDataset.name))
            demo_case = session.scalar(select(Case).where(Case.id == report.case_id))
    finally:
        engine.dispose()

    print(
        "demo preparada: "
        f"case={report.case_id} title={demo_case.title if demo_case else '-'} "
        f"findings={findings} dataset={dataset.name if dataset else '-'} "
        f"public_documents={public_documents} chunks={chunks} "
        f"corpus_outcomes={[(item.status, item.chunks) for item in outcomes]}"
    )
    if failed:
        print(f"fuentes fallidas: {len(failed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
