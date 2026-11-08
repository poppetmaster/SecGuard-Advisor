"""Pruebas de nombres y alcances de colecciones."""

import pytest

from secguard_advisor.retrieval.collections import (
    CollectionScope,
    case_scope,
    collection_name,
    public_scope,
    validate_collection_name,
)


def test_public_and_case_names_are_distinct() -> None:
    public = collection_name(public_scope(), "embeddinggemma", 768)
    case = collection_name(case_scope("a" * 32), "embeddinggemma", 768)

    assert public == "public__embeddinggemma__768"
    assert case == f"case__{'a' * 32}__embeddinggemma__768"
    assert public != case
    assert len(case) <= 63


def test_model_slug_is_sanitized_and_limited() -> None:
    name = collection_name(public_scope(), "Model/With:Symbols" * 4, 768)

    assert name.startswith("public__")
    assert ":" not in name
    assert "/" not in name
    assert len(name) <= 63


def test_invalid_case_id_is_rejected() -> None:
    with pytest.raises(ValueError):
        case_scope("not-a-case")


def test_public_scope_cannot_have_case() -> None:
    with pytest.raises(ValueError):
        CollectionScope(kind="public", case_id="a" * 32)


def test_invalid_dimension_is_rejected() -> None:
    with pytest.raises(ValueError):
        collection_name(public_scope(), "embeddinggemma", 0)


def test_invalid_collection_names_are_rejected() -> None:
    for name in ("ab", "a" * 64, "a..b", "-inicio", "fin-"):
        with pytest.raises(ValueError):
            validate_collection_name(name)
