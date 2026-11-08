"""Pruebas de indexación y reconstrucción sobre Chroma."""

from pathlib import Path

from secguard_advisor.retrieval.collections import case_scope
from secguard_advisor.retrieval.index import ChromaIndex, IndexedChunk


def _chunk(
    chunk_id: str,
    text: str,
    embedding: list[float],
    *,
    version_id: str = "v" * 32,
) -> IndexedChunk:
    return IndexedChunk(
        chunk_id=chunk_id,
        text=text,
        embedding=embedding,
        document_id="d" * 32,
        version_id=version_id,
        origin="case_evidence",
        source_id=None,
        page=1,
        section=None,
        locator=f"p:1#{chunk_id}",
    )


def test_upsert_query_and_rebuild(tmp_path: Path) -> None:
    index = ChromaIndex(tmp_path / "chroma")
    scope = case_scope("a" * 32)
    chunks = [
        _chunk("c1", "primero", [1.0, 0.0, 0.0]),
        _chunk("c2", "segundo", [0.0, 1.0, 0.0]),
    ]

    index.upsert(scope, "embeddinggemma", 3, chunks)
    assert index.count(scope, "embeddinggemma", 3) == 2

    hits = index.query(scope, "embeddinggemma", 3, [1.0, 0.0, 0.0], top_k=2)
    assert len(hits) == 2
    assert hits[0].chunk_id == "c1"
    assert hits[0].text == "primero"

    index.rebuild(scope, "embeddinggemma", 3, [chunks[1]])
    assert index.count(scope, "embeddinggemma", 3) == 1


def test_delete_version_removes_its_chunks(tmp_path: Path) -> None:
    index = ChromaIndex(tmp_path / "chroma")
    scope = case_scope("b" * 32)
    index.upsert(
        scope,
        "embeddinggemma",
        3,
        [
            _chunk("c1", "uno", [1.0, 0.0, 0.0], version_id="v1" + "0" * 30),
            _chunk("c2", "dos", [0.0, 1.0, 0.0], version_id="v2" + "0" * 30),
        ],
    )

    index.delete_version(scope, "embeddinggemma", 3, "v1" + "0" * 30)

    assert index.count(scope, "embeddinggemma", 3) == 1
