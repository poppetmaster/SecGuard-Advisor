"""Pruebas unitarias del adaptador Qdrant (UUIDv5, payload y score)."""

from __future__ import annotations

from pathlib import Path

import pytest
from qdrant_client import QdrantClient

from secguard_advisor.retrieval.collections import case_scope, public_scope
from secguard_advisor.retrieval.errors import (
    CaseIndexUnavailable,
    IndexConfigurationError,
    PublicIndexUnavailable,
)
from secguard_advisor.retrieval.index import (
    IndexedChunk,
    QdrantIndex,
    chunk_payload,
    hit_from_point,
    point_id,
)

INSTANCE = "test-local"
CASE_ID = "a" * 32


def _chunk(chunk_id: str, version_id: str = "v" * 32, text: str = "texto secreto") -> IndexedChunk:
    return IndexedChunk(
        chunk_id=chunk_id,
        text=text,
        embedding=[1.0, 0.0, 0.0, 0.0],
        document_id="d" * 32,
        version_id=version_id,
        origin="public_corpus",
        source_id="nist",
        page=3,
        section="Resumen",
        locator="p. 3",
        document_title="Documento",
        declared_version="1.0",
        chunk_index=0,
        embedding_model="embeddinggemma",
        embedding_dim=4,
    )


@pytest.fixture()
def index(tmp_path: Path):
    client = QdrantClient(path=str(tmp_path / "qdrant"))
    adapter = QdrantIndex(
        url="http://127.0.0.1:6333",
        instance_id=INSTANCE,
        client=client,
    )
    yield adapter
    adapter.close()


def test_point_id_is_deterministic_and_unique() -> None:
    first = point_id("a" * 32)
    second = point_id("a" * 32)

    assert first == second
    assert first != point_id("b" * 32)
    assert len(first) == 36


def test_payload_maps_provenance_without_text() -> None:
    payload = chunk_payload(_chunk("a" * 32))

    assert payload["chunk_id"] == "a" * 32
    assert payload["version_id"] == "v" * 32
    assert payload["origin"] == "public_corpus"
    assert payload["locator"] == "p. 3"
    assert payload["document_title"] == "Documento"
    assert "text" not in payload
    assert "texto secreto" not in str(payload)


def test_upsert_query_and_count_use_scores(index: QdrantIndex) -> None:
    index.upsert(public_scope(), "embeddinggemma", 4, [_chunk("a" * 32)])

    hits = index.query(public_scope(), "embeddinggemma", 4, [1.0, 0.0, 0.0, 0.0])

    assert index.count(public_scope(), "embeddinggemma", 4) == 1
    assert len(hits) == 1
    assert hits[0].chunk_id == "a" * 32
    assert hits[0].score == pytest.approx(1.0)
    assert hits[0].distance is None
    assert "text" not in hits[0].metadata
    assert hit_from_point(type("P", (), {"payload": hits[0].metadata, "score": 0.5})()).score == 0.5


def test_upsert_is_idempotent_by_chunk_id(index: QdrantIndex) -> None:
    index.upsert(public_scope(), "embeddinggemma", 4, [_chunk("a" * 32)])
    index.upsert(public_scope(), "embeddinggemma", 4, [_chunk("a" * 32)])

    assert index.count(public_scope(), "embeddinggemma", 4) == 1


def test_delete_version_and_ids(index: QdrantIndex) -> None:
    index.upsert(
        public_scope(),
        "embeddinggemma",
        4,
        [_chunk("a" * 32, version_id="v" * 32), _chunk("b" * 32, version_id="w" * 32)],
    )

    index.delete_version(public_scope(), "embeddinggemma", 4, "v" * 32)

    assert index.count(public_scope(), "embeddinggemma", 4) == 1
    index.delete_ids(public_scope(), "embeddinggemma", 4, ["b" * 32])
    assert index.count(public_scope(), "embeddinggemma", 4) == 0


def test_missing_alias_raises_classified_errors(index: QdrantIndex) -> None:
    with pytest.raises(PublicIndexUnavailable):
        index.query(public_scope(), "embeddinggemma", 4, [1.0, 0.0, 0.0, 0.0])

    with pytest.raises(CaseIndexUnavailable):
        index.query(case_scope(CASE_ID), "embeddinggemma", 4, [1.0, 0.0, 0.0, 0.0])


def test_missing_instance_id_is_a_configuration_error() -> None:
    with pytest.raises(IndexConfigurationError):
        QdrantIndex(url="http://127.0.0.1:6333", instance_id=None)


def test_case_scope_never_mixes_with_public(index: QdrantIndex) -> None:
    index.upsert(case_scope(CASE_ID), "embeddinggemma", 4, [_chunk("a" * 32)])

    with pytest.raises(PublicIndexUnavailable):
        index.query(public_scope(), "embeddinggemma", 4, [1.0, 0.0, 0.0, 0.0])

    hits = index.query(case_scope(CASE_ID), "embeddinggemma", 4, [1.0, 0.0, 0.0, 0.0])
    assert hits[0].chunk_id == "a" * 32
