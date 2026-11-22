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
from secguard_advisor.retrieval.collections import case_scope, public_scope
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


def _search(settings, factory, index, embedder, case_id):
    from secguard_advisor.retrieval.search import search_documents

    with factory() as session:
        return search_documents(
            session,
            scope=CaseScope(case_id=case_id),
            query="consulta",
            embedder=embedder,
            index=index,
            top_k=10,
            min_score=0.0,
        )


def test_evidence_keeps_queried_generations_after_alias_switch(environment) -> None:
    settings, factory, index, embedder, case_id = environment
    result = _search(settings, factory, index, embedder, case_id)
    public_generation = result.public_evidence["generation"]
    case_generation = result.case_evidence["generation"]

    for scope in (public_scope(), case_scope(case_id)):
        _generation, collection = index.create_generation(scope, embedder.model, embedder.dimension)
        index.activate_alias(scope, embedder.model, embedder.dimension, collection)

    evidence = nodes._index_evidence(result)

    assert evidence["public_generation"] == public_generation
    assert evidence["generation"] == case_generation
    assert (
        index.describe(public_scope(), embedder.model, embedder.dimension)["generation"]
        != public_generation
    )


def test_zero_hit_scope_keeps_the_identity_it_queried(environment) -> None:
    settings, factory, index, embedder, case_id = environment
    _generation, empty_collection = index.create_generation(
        public_scope(), embedder.model, embedder.dimension
    )
    index.activate_alias(public_scope(), embedder.model, embedder.dimension, empty_collection)
    empty_generation = empty_collection.rsplit("__g", 1)[-1]

    result = _search(settings, factory, index, embedder, case_id)
    assert result.public_evidence["generation"] == empty_generation
    assert all(hit.origin != "public_corpus" for hit in result.hits)

    _other, other_collection = index.create_generation(
        public_scope(), embedder.model, embedder.dimension
    )
    index.activate_alias(public_scope(), embedder.model, embedder.dimension, other_collection)

    evidence = nodes._index_evidence(result)
    assert evidence["public_generation"] == empty_generation


class _IdentityIndex:
    def __init__(self) -> None:
        self.public = {"generation": "A-public", "collection_alias": "alias-public"}
        self.case = {"generation": "A-case", "collection_alias": "alias-case"}

    def query_with_identity(self, scope, _model, _dimension, _embedding, *, top_k=6):
        return [], (self.public if scope.kind == "public" else self.case)

    def describe(self, *_args, **_kwargs):
        return {"generation": "B", "collection_alias": "alias-B"}


def test_retrieve_does_not_use_describe_after_search(environment) -> None:
    settings, factory, _index, embedder, case_id = environment
    stub = _IdentityIndex()
    runtime = SimpleNamespace(
        deps=SimpleNamespace(settings=settings, embedder=embedder, index=stub),
        question="consulta",
        factory=factory,
        scope=CaseScope(case_id=case_id),
    )
    config = {"configurable": {"runtime": runtime, "tracer": DummyTracer()}}

    result = nodes.retrieve({"history": (), "steps": ()}, config)
    detail = result["steps"][-1].detail

    assert detail["generation"] == "A-case"
    assert detail["public_generation"] == "A-public"
    assert detail["vector_backend"] is None
