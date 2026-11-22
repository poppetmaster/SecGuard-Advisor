"""Contrato de evidencia del paso retrieve con Qdrant."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from qdrant_client import QdrantClient
from tests.fixtures.corpus import NullEmbedder, create_case, seed_document

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.conversation import nodes
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.retrieval.index import QdrantIndex

INSTANCE = "test-local"


class DummyTracer:
    def operation(self, *_args, **_kwargs) -> None:
        return None


@pytest.fixture()
def environment(tmp_path: Path):
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
        case_id = create_case(session, "Caso evidencia")
        session.commit()
    seed_document(
        factory,
        texts=["control público"],
        source_id="sample",
        index=index,
        embedder=embedder,
    )
    seed_document(
        factory,
        texts=["evidencia del caso"],
        case_id=case_id,
        index=index,
        embedder=embedder,
    )
    yield settings, factory, index, embedder, case_id
    index.close()
    engine.dispose()


def test_retrieve_step_records_index_identity(environment) -> None:
    settings, factory, index, embedder, case_id = environment
    runtime = SimpleNamespace(
        deps=SimpleNamespace(settings=settings, embedder=embedder, index=index),
        question="¿qué controles aplicar?",
        factory=factory,
        scope=CaseScope(case_id=case_id),
    )
    config = {"configurable": {"runtime": runtime, "tracer": DummyTracer()}}

    result = nodes.retrieve({"history": (), "steps": ()}, config)
    detail = result["steps"][-1].detail

    assert detail["vector_backend"] == "qdrant"
    assert detail["instance_id"] == INSTANCE
    assert detail["qdrant_version"]
    assert detail["embedding_model"] == NullEmbedder.model
    assert detail["embedding_dim"] == NullEmbedder.dimension
    assert f"__case__{case_id}__" in detail["collection_alias"]
    assert detail["generation"]
    assert "__public__" in detail["public_alias"]
    assert detail["score_metric"] == "cosine"
    assert detail["error_code"] is None
    assert "text" not in detail
