"""Aislamiento de dos instancias con el mismo caso en un servidor Qdrant."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from qdrant_client import QdrantClient

from secguard_advisor.retrieval import instance
from secguard_advisor.retrieval.collections import case_scope, public_scope
from secguard_advisor.retrieval.errors import IndexConfigurationError
from secguard_advisor.retrieval.index import IndexedChunk, QdrantIndex

CASE_ID = "a" * 32
MODEL = "fake-embedding"
DIM = 4


def _chunk(chunk_id: str, text: str, vector: list[float], origin: str) -> IndexedChunk:
    return IndexedChunk(
        chunk_id=chunk_id,
        text=text,
        embedding=vector,
        document_id="d" * 32,
        version_id="v" * 32,
        origin=origin,
        source_id="sample" if origin == "public_corpus" else None,
        page=1,
        section=None,
        locator="p. 1",
        document_title=text,
        embedding_model=MODEL,
        embedding_dim=DIM,
    )


@pytest.fixture()
def environment(tmp_path: Path):
    client = QdrantClient(path=str(tmp_path / "qdrant"))
    first_storage = tmp_path / "storage-a"
    second_storage = tmp_path / "storage-b"
    first = QdrantIndex(
        url="http://127.0.0.1:6333",
        instance_id="inst-a",
        client=client,
        storage_dir=first_storage,
    )
    second = QdrantIndex(
        url="http://127.0.0.1:6333",
        instance_id="inst-b",
        client=client,
        storage_dir=second_storage,
    )
    first.upsert(
        case_scope(CASE_ID),
        MODEL,
        DIM,
        [_chunk("1" * 32, "caso A", [1.0, 0, 0, 0], "case_evidence")],
    )
    second.upsert(
        case_scope(CASE_ID),
        MODEL,
        DIM,
        [_chunk("2" * 32, "caso B", [0, 1.0, 0, 0], "case_evidence")],
    )
    first.upsert(
        public_scope(), MODEL, DIM, [_chunk("3" * 32, "público A", [1.0, 0, 0, 0], "public_corpus")]
    )
    second.upsert(
        public_scope(), MODEL, DIM, [_chunk("4" * 32, "público B", [0, 1.0, 0, 0], "public_corpus")]
    )
    yield first, second, client, first_storage
    first.close()
    second.close()


def test_same_case_and_public_are_isolated_per_instance(environment) -> None:
    first, second, _client, _storage = environment

    hits_a = first.query(case_scope(CASE_ID), MODEL, DIM, [1.0, 0, 0, 0], top_k=10)
    hits_b = second.query(case_scope(CASE_ID), MODEL, DIM, [0, 1.0, 0, 0], top_k=10)
    public_a = first.query(public_scope(), MODEL, DIM, [1.0, 0, 0, 0], top_k=10)
    public_b = second.query(public_scope(), MODEL, DIM, [0, 1.0, 0, 0], top_k=10)

    assert {hit.chunk_id for hit in hits_a} == {"1" * 32}
    assert {hit.chunk_id for hit in hits_b} == {"2" * 32}
    assert {hit.chunk_id for hit in public_a} == {"3" * 32}
    assert {hit.chunk_id for hit in public_b} == {"4" * 32}


def test_collections_aliases_and_evidence_name_the_instance(environment) -> None:
    first, _second, client, _storage = environment
    aliases = {entry.alias_name: entry.collection_name for entry in client.get_aliases().aliases}

    assert any(name.startswith("secguard__inst-a__") for name in aliases)
    assert any(name.startswith("secguard__inst-b__") for name in aliases)
    assert len({name for name in aliases if "__case__" in name}) == 2

    _hits, identity = first.query_with_identity(case_scope(CASE_ID), MODEL, DIM, [1.0, 0, 0, 0])
    assert identity["instance_id"] == "inst-a"
    assert identity["generation"]
    assert identity["collection_alias"].startswith("secguard__inst-a__")


def test_copied_storage_fails_closed_without_writing(environment, tmp_path: Path) -> None:
    _first, _second, client, first_storage = environment
    copied = tmp_path / "storage-copy"
    (copied / "qdrant-control" / "instances").mkdir(parents=True)
    marker = instance.marker_path(first_storage, "inst-a")
    copied_marker = copied / "qdrant-control" / "instances" / marker.name
    copied_marker.write_text(marker.read_text(encoding="utf-8"), encoding="utf-8")
    before_marker = copied_marker.read_text(encoding="utf-8")
    before_aliases = {entry.alias_name for entry in client.get_aliases().aliases}
    before_collections = {item.name for item in client.get_collections().collections}

    copy_index = QdrantIndex(
        url="http://127.0.0.1:6333",
        instance_id="inst-a",
        client=client,
        storage_dir=copied,
    )
    with pytest.raises(IndexConfigurationError):
        copy_index.query(case_scope(CASE_ID), MODEL, DIM, [1.0, 0, 0, 0])

    assert copied_marker.read_text(encoding="utf-8") == before_marker
    assert {entry.alias_name for entry in client.get_aliases().aliases} == before_aliases
    assert {item.name for item in client.get_collections().collections} == before_collections
    assert json.loads(before_marker)["instance_id"] == "inst-a"
