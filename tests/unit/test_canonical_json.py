"""Canonical JSON and hashing."""

from secguard_advisor.reports.canonical import canonical_json, canonical_sha256, sha256_hex


def test_canonical_json_is_stable_for_nested_values() -> None:
    left = {"b": 2, "a": {"y": "ñ", "x": [1, 2]}}
    right = {"a": {"x": [1, 2], "y": "ñ"}, "b": 2}
    assert canonical_json(left) == canonical_json(right)
    assert canonical_sha256(left) == canonical_sha256(right)
    assert len(sha256_hex("texto")) == 64
