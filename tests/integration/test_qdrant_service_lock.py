"""El servicio de documentos respeta el lock de reconstrucción."""

from __future__ import annotations

from pathlib import Path

import pytest
from qdrant_client import QdrantClient
from tests.fixtures.corpus import NullEmbedder, create_case

from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.documents.service import ingest_document
from secguard_advisor.documents.validation import validate_bytes
from secguard_advisor.retrieval import instance
from secguard_advisor.retrieval.index import QdrantIndex

INSTANCE = "test-local"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


def test_ingestion_is_rejected_while_rebuild_holds_the_lock(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        storage_dir=tmp_path / "storage",
        instance_id=INSTANCE,
        embedding_dim=NullEmbedder.dimension,
    )
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    client = QdrantClient(path=str(tmp_path / "qdrant"))
    index = QdrantIndex(url="http://127.0.0.1:6333", instance_id=INSTANCE, client=client)
    embedder = NullEmbedder()
    with factory() as session:
        case_id = create_case(session, "Caso")
        session.commit()
    upload = validate_bytes(
        "sample.pdf", (FIXTURES / "sample.pdf").read_bytes(), settings.max_upload_bytes
    )
    try:
        with (
            instance.acquire_instance_lock(settings.storage_dir, INSTANCE, "rebuild"),
            pytest.raises(instance.InstanceLockBusy) as error,
            ingest_document(
                factory,
                settings,
                scope_key=f"case:{case_id}",
                case_id=case_id,
                origin="case_evidence",
                source_id=None,
                title="Evidencia",
                upload=upload,
                embedder=embedder,
                index=index,
                declared_version=None,
                retrieved_at=None,
                license=None,
                store_original_file=True,
            ),
        ):
            pass
    finally:
        index.close()
        engine.dispose()

    assert instance.lock_conflict_code(error.value.owner) == "reconstruction_in_progress"
