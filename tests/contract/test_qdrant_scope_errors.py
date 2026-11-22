"""Alcance vacío frente a índice ausente en la recuperación."""

from __future__ import annotations

from pathlib import Path

import pytest
from qdrant_client import QdrantClient
from tests.fixtures.corpus import NullEmbedder, create_case, seed_document

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.retrieval.collections import public_scope
from secguard_advisor.retrieval.errors import (
    CaseIndexUnavailable,
    PublicIndexUnavailable,
    QdrantUnavailable,
)
from secguard_advisor.retrieval.index import QdrantIndex
from secguard_advisor.retrieval.search import search_documents

INSTANCE = "test-local"
MODEL = NullEmbedder.model
DIM = NullEmbedder.dimension


@pytest.fixture()
def environment(tmp_path: Path):
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
    client = QdrantClient(path=str(tmp_path / "qdrant"))
    index = QdrantIndex(url="http://127.0.0.1:6333", instance_id=INSTANCE, client=client)
    embedder = NullEmbedder()
    with factory() as session:
        case_id = create_case(session, "Caso")
        session.commit()
    yield settings, factory, index, embedder, case_id
    index.close()
    engine.dispose()


def _search(factory, index, embedder, case_id):
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


def test_case_without_documents_queries_public(environment) -> None:
    _, factory, index, embedder, case_id = environment
    public = seed_document(
        factory, texts=["público"], source_id="sample", index=index, embedder=embedder
    )

    result = _search(factory, index, embedder, case_id)

    assert result.status == "ok"
    assert {hit.document_id for hit in result.hits} == {public.document_id}


def test_expected_case_without_alias_is_an_index_error(environment) -> None:
    _, factory, index, embedder, case_id = environment
    seed_document(factory, texts=["privado"], case_id=case_id, embedder=embedder)

    with pytest.raises(CaseIndexUnavailable):
        _search(factory, index, embedder, case_id)


def test_expected_public_without_alias_is_an_index_error(environment) -> None:
    _, factory, index, embedder, case_id = environment
    seed_document(factory, texts=["público"], source_id="sample", embedder=embedder)

    with pytest.raises(PublicIndexUnavailable):
        _search(factory, index, embedder, case_id)


def test_empty_public_is_omitted_and_case_continues(environment) -> None:
    _, factory, index, embedder, case_id = environment
    private = seed_document(
        factory, texts=["privado"], case_id=case_id, index=index, embedder=embedder
    )

    result = _search(factory, index, embedder, case_id)

    assert result.status == "ok"
    assert {hit.document_id for hit in result.hits} == {private.document_id}


def test_alias_without_hits_is_empty_not_an_error(environment) -> None:
    _, factory, index, embedder, case_id = environment
    seed_document(factory, texts=["público"], source_id="sample", embedder=embedder)
    _generation, collection = index.create_generation(public_scope(), MODEL, DIM)
    index.activate_alias(public_scope(), MODEL, DIM, collection)

    result = _search(factory, index, embedder, case_id)

    assert result.status == "empty"
    assert result.hits == ()


def test_qdrant_down_is_infrastructure_error(environment) -> None:
    _settings, factory, _index, embedder, case_id = environment
    seed_document(factory, texts=["privado"], case_id=case_id, embedder=embedder)
    down = QdrantIndex(url="http://127.0.0.1:1", instance_id=INSTANCE, timeout=0.5)
    try:
        with pytest.raises(QdrantUnavailable):
            _search(factory, down, embedder, case_id)
    finally:
        down.close()
