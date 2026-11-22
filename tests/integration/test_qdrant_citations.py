"""Versiones vigentes, citas históricas y aislamiento con Qdrant."""

from __future__ import annotations

from pathlib import Path

import pytest
from qdrant_client import QdrantClient
from tests.fixtures.corpus import NullEmbedder, create_case, seed_document

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.retrieval.citations import check_citation
from secguard_advisor.retrieval.index import QdrantIndex
from secguard_advisor.retrieval.search import search_documents

INSTANCE = "test-local"


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
        case_a = create_case(session, "Caso A")
        case_b = create_case(session, "Caso B")
        session.commit()
    first = seed_document(
        factory,
        texts=["texto versión uno"],
        source_id="sample",
        index=index,
        embedder=embedder,
        pages=[1],
    )
    second = seed_document(
        factory,
        texts=["texto versión dos"],
        source_id="sample",
        index=index,
        embedder=embedder,
        pages=[2],
        new_version=True,
    )
    doc_a = seed_document(
        factory,
        texts=["evidencia del caso A"],
        case_id=case_a,
        index=index,
        embedder=embedder,
        pages=[3],
    )
    doc_b = seed_document(
        factory,
        texts=["evidencia del caso B"],
        case_id=case_b,
        index=index,
        embedder=embedder,
        pages=[4],
    )
    yield settings, factory, index, embedder, case_a, case_b, first, second, doc_a, doc_b
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


def test_superseded_version_is_not_returned_and_history_still_resolves(environment) -> None:
    _, factory, index, embedder, case_a, _, first, second, *_ = environment

    result = _search(factory, index, embedder, case_a)
    ids = {hit.chunk_id for hit in result.hits}

    assert set(second.chunk_ids) <= ids
    assert not ids & set(first.chunk_ids)

    with factory() as session:
        history = check_citation(
            session,
            CaseScope(case_id=case_a),
            chunk_id=first.chunk_ids[0],
            version_id=first.version_id,
            page=1,
            section=None,
            quote="texto versión uno",
        )
        current = check_citation(
            session,
            CaseScope(case_id=case_a),
            chunk_id=second.chunk_ids[0],
            version_id=second.version_id,
            page=2,
            section=None,
            quote="texto versión dos",
        )

    assert history.valid
    assert current.valid


def test_case_documents_do_not_cross_and_versions_are_isolated(environment) -> None:
    _, factory, index, embedder, case_a, case_b, _, _, doc_a, doc_b = environment

    result_a = _search(factory, index, embedder, case_a)
    result_b = _search(factory, index, embedder, case_b)
    ids_a = {hit.document_id for hit in result_a.hits}
    ids_b = {hit.document_id for hit in result_b.hits}

    assert doc_a.document_id in ids_a
    assert doc_b.document_id not in ids_a
    assert doc_b.document_id in ids_b
    assert doc_a.document_id not in ids_b
