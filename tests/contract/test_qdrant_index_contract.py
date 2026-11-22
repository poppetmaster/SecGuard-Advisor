"""Contrato de nombres, alias y payload de Qdrant."""

from __future__ import annotations

import pytest
from qdrant_client import QdrantClient

from secguard_advisor.retrieval.collections import (
    case_scope,
    instance_alias_name,
    instance_collection_name,
    new_generation_id,
    public_scope,
)
from secguard_advisor.retrieval.index import IndexedChunk, QdrantIndex, chunk_payload

INSTANCE = "test-local"
OTHER_INSTANCE = "test-otra"
CASE = "a" * 32


def _name(instance: str, scope, generation: str = "20261122T100000000000Z") -> str:
    return instance_collection_name(instance, scope, "embeddinggemma", 768, generation)


def test_names_include_instance_scope_model_dimension_and_generation() -> None:
    public = _name(INSTANCE, public_scope())
    case = _name(INSTANCE, case_scope(CASE))

    assert public.startswith(f"secguard__{INSTANCE}__public__embeddinggemma__768__g")
    assert case.startswith(f"secguard__{INSTANCE}__case__{CASE}__embeddinggemma__768__g")
    assert public != case


def test_instances_and_generations_are_isolated() -> None:
    assert _name(INSTANCE, public_scope()) != _name(OTHER_INSTANCE, public_scope())
    assert _name(INSTANCE, public_scope()) != _name(
        INSTANCE, public_scope(), "20261122T100001000000Z"
    )


def test_alias_is_stable_per_instance_and_scope() -> None:
    alias = instance_alias_name(INSTANCE, public_scope(), "embeddinggemma", 768)

    assert alias == f"secguard__{INSTANCE}__public__embeddinggemma__768__active"
    assert instance_alias_name(INSTANCE, case_scope(CASE), "embeddinggemma", 768).endswith(
        "__active"
    )
    assert instance_alias_name(OTHER_INSTANCE, public_scope(), "embeddinggemma", 768) != alias


def test_invalid_inputs_are_rejected() -> None:
    with pytest.raises(ValueError):
        _name("Bad Instance", public_scope())
    with pytest.raises(ValueError):
        instance_collection_name(INSTANCE, public_scope(), "m", 0, new_generation_id())
    with pytest.raises(ValueError):
        instance_collection_name(INSTANCE, public_scope(), "m", 768, "no-generation")


def test_alias_resolves_to_the_active_collection_after_upsert(tmp_path) -> None:
    client = QdrantClient(path=str(tmp_path / "qdrant"))
    adapter = QdrantIndex(url="http://127.0.0.1:6333", instance_id=INSTANCE, client=client)
    try:
        chunk = IndexedChunk(
            chunk_id="c" * 32,
            text="texto que no debe copiarse",
            embedding=[0.1, 0.2, 0.3, 0.4],
            document_id="d" * 32,
            version_id="v" * 32,
            origin="case_evidence",
            source_id=None,
            page=1,
            section=None,
            locator="p. 1",
        )
        adapter.upsert(case_scope(CASE), "embeddinggemma", 4, [chunk])

        aliases = {a.alias_name: a.collection_name for a in client.get_aliases().aliases}
        alias = instance_alias_name(INSTANCE, case_scope(CASE), "embeddinggemma", 4)
        assert alias in aliases
        assert aliases[alias].startswith(
            f"secguard__{INSTANCE}__case__{CASE}__embeddinggemma__4__g"
        )
        assert "text" not in chunk_payload(chunk)
    finally:
        adapter.close()
