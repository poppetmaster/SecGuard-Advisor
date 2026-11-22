"""Pruebas de nombres y alcances de colecciones Qdrant."""

import pytest

from secguard_advisor.retrieval.collections import (
    CollectionScope,
    case_scope,
    instance_alias_name,
    instance_collection_name,
    new_generation_id,
    public_scope,
    validate_qdrant_name,
)


def test_public_and_case_names_are_distinct() -> None:
    generation = new_generation_id()
    public = instance_collection_name(
        "local-dev", public_scope(), "embeddinggemma", 768, generation
    )
    case = instance_collection_name(
        "local-dev", case_scope("a" * 32), "embeddinggemma", 768, generation
    )

    assert public.startswith("secguard__local-dev__public__embeddinggemma__768__g")
    assert case.startswith(f"secguard__local-dev__case__{'a' * 32}__")
    assert public != case


def test_model_slug_is_sanitized_and_limited() -> None:
    name = instance_collection_name(
        "local-dev", public_scope(), "Model/With:Symbols" * 4, 768, new_generation_id()
    )

    assert ":" not in name
    assert "/" not in name
    assert len(name) <= 255


def test_alias_is_stable_and_namespaced() -> None:
    alias = instance_alias_name("local-dev", public_scope(), "embeddinggemma", 768)

    assert alias == "secguard__local-dev__public__embeddinggemma__768__active"


def test_invalid_case_id_is_rejected() -> None:
    with pytest.raises(ValueError):
        case_scope("not-a-case")


def test_public_scope_cannot_have_case() -> None:
    with pytest.raises(ValueError):
        CollectionScope(kind="public", case_id="a" * 32)


def test_invalid_dimension_is_rejected() -> None:
    with pytest.raises(ValueError):
        instance_collection_name(
            "local-dev", public_scope(), "embeddinggemma", 0, new_generation_id()
        )


def test_invalid_names_are_rejected() -> None:
    for name in ("ab", "a" * 256, "a..b", "-inicio", "fin-"):
        with pytest.raises(ValueError):
            validate_qdrant_name(name)
