"""Pruebas de recuperación documental fusionada y aislada."""

from pathlib import Path

import pytest
from sqlalchemy import select
from tests.fixtures.corpus import create_case, seed_document
from tests.fixtures.fakes import FakeEmbedder

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import DocumentChunk, DocumentVersion
from secguard_advisor.retrieval.index import ChromaIndex, QueryHit


def _hit(chunk_id: str, text: str, distance: float, **metadata) -> QueryHit:
    return QueryHit(
        chunk_id=chunk_id,
        text=text,
        metadata={"document_id": metadata.get("document_id", "")},
        distance=distance,
    )


class StubIndex:
    """Índice guionizado que devuelve distancias controladas."""

    def __init__(self, by_scope: dict[str, list[QueryHit]]) -> None:
        self.by_scope = by_scope
        self.queried: list[tuple[str, str | None]] = []

    def query(self, scope, model, dimension, embedding, *, top_k=6) -> list[QueryHit]:
        key = scope.case_id if scope.kind == "case" else "public"
        self.queried.append((scope.kind, scope.case_id))
        return self.by_scope.get(key, [])[:top_k]


@pytest.fixture
def context(tmp_path: Path):
    engine = create_engine_for_url(f"sqlite:///{tmp_path / 'search.sqlite3'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        case_a = create_case(session, "Caso A")
        case_b = create_case(session, "Caso B")
        session.commit()
    yield factory, case_a, case_b
    engine.dispose()


def _search(factory, case_id, index, *, min_score: float = 0.0, top_k: int = 6):
    from secguard_advisor.retrieval.search import search_documents

    with factory() as session:
        return search_documents(
            session,
            scope=CaseScope(case_id=case_id),
            query="¿qué controles aplicar?",
            embedder=FakeEmbedder(),
            index=index,
            top_k=top_k,
            min_score=min_score,
        )


def test_public_and_case_hits_are_fused_by_score(context) -> None:
    factory, case_a, _case_b = context
    public = seed_document(factory, texts=["control publico"], source_id="csf2", pages=[1])
    private = seed_document(factory, texts=["control privado"], case_id=case_a, pages=[2])
    index = StubIndex(
        {
            "public": [_hit(public.chunk_ids[0], "control publico", 0.30)],
            case_a: [_hit(private.chunk_ids[0], "control privado", 0.10)],
        }
    )

    result = _search(factory, case_a, index)

    assert result.status == "ok"
    assert [hit.chunk_id for hit in result.hits] == [
        private.chunk_ids[0],
        public.chunk_ids[0],
    ]
    assert [hit.origin for hit in result.hits] == ["case_evidence", "public_corpus"]
    assert result.hits[0].score == pytest.approx(0.9)
    assert result.hits[0].document_title == "Documento"


def test_threshold_filters_weak_candidates(context) -> None:
    factory, case_a, _case_b = context
    strong = seed_document(factory, texts=["fuerte"], case_id=case_a, pages=[1])
    weak = seed_document(factory, texts=["debil"], case_id=case_a, pages=[2])
    index = StubIndex(
        {
            case_a: [
                _hit(strong.chunk_ids[0], "fuerte", 0.10),
                _hit(weak.chunk_ids[0], "debil", 0.92),
            ]
        }
    )

    result = _search(factory, case_a, index, min_score=0.5)

    assert [hit.chunk_id for hit in result.hits] == [strong.chunk_ids[0]]


def test_no_candidates_is_empty_not_failure(context) -> None:
    factory, case_a, _case_b = context
    index = StubIndex({})

    result = _search(factory, case_a, index)

    assert result.status == "empty"
    assert result.hits == ()
    assert index.queried == [("public", None), ("case", case_a)]


def test_superseded_version_is_excluded_but_history_is_kept(context) -> None:
    factory, case_a, _case_b = context
    first = seed_document(factory, texts=["version uno"], case_id=case_a, pages=[1])
    second = seed_document(
        factory, texts=["version dos"], case_id=case_a, pages=[1], new_version=True
    )
    index = StubIndex(
        {
            case_a: [
                _hit(first.chunk_ids[0], "version uno", 0.05),
                _hit(second.chunk_ids[0], "version dos", 0.20),
            ]
        }
    )

    result = _search(factory, case_a, index)

    assert [hit.chunk_id for hit in result.hits] == [second.chunk_ids[0]]
    with factory() as session:
        old_version = session.get(DocumentVersion, first.version_id)
        old_chunks = list(
            session.scalars(
                select(DocumentChunk).where(DocumentChunk.version_id == first.version_id)
            )
        )
        assert old_version.status == "superseded"
        assert old_chunks and old_chunks[0].text == "version uno"


def test_chunks_of_another_case_are_never_returned(context) -> None:
    factory, case_a, case_b = context
    private_a = seed_document(factory, texts=["secreto A"], case_id=case_a, pages=[1])
    private_b = seed_document(factory, texts=["secreto B"], case_id=case_b, pages=[1])
    index = StubIndex(
        {
            case_a: [
                _hit(private_a.chunk_ids[0], "secreto A", 0.1),
                _hit(private_b.chunk_ids[0], "secreto B", 0.2),
            ],
            case_b: [_hit(private_b.chunk_ids[0], "secreto B", 0.1)],
        }
    )

    result_a = _search(factory, case_a, index)
    result_b = _search(factory, case_b, index)

    assert [hit.chunk_id for hit in result_a.hits] == [private_a.chunk_ids[0]]
    assert [hit.chunk_id for hit in result_b.hits] == [private_b.chunk_ids[0]]


def test_real_chroma_keeps_case_isolation_and_shared_public(tmp_path: Path, context) -> None:
    from secguard_advisor.retrieval.search import search_documents

    factory, case_a, case_b = context
    embedder = FakeEmbedder()
    index = ChromaIndex(tmp_path / "chroma")
    public = seed_document(
        factory,
        texts=["guia publica de riesgos"],
        index=index,
        embedder=embedder,
        source_id="csf2",
        pages=[1],
    )
    private_a = seed_document(
        factory,
        texts=["evidencia privada del caso A"],
        index=index,
        embedder=embedder,
        case_id=case_a,
        pages=[1],
    )
    private_b = seed_document(
        factory,
        texts=["evidencia privada del caso B"],
        index=index,
        embedder=embedder,
        case_id=case_b,
        pages=[1],
    )

    def run(case_id: str):
        with factory() as session:
            return search_documents(
                session,
                scope=CaseScope(case_id=case_id),
                query="evidencia",
                embedder=embedder,
                index=index,
                top_k=10,
                min_score=0.0,
            )

    hits_a = {hit.chunk_id for hit in run(case_a).hits}
    hits_b = {hit.chunk_id for hit in run(case_b).hits}

    assert public.chunk_ids[0] in hits_a
    assert public.chunk_ids[0] in hits_b
    assert private_a.chunk_ids[0] in hits_a
    assert private_a.chunk_ids[0] not in hits_b
    assert private_b.chunk_ids[0] in hits_b
    assert private_b.chunk_ids[0] not in hits_a
