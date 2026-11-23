"""Canonical JSON and hashing shared by datasets, charts and manifests."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(value: Any) -> str:
    """Serialize with stable ordering and no insignificant whitespace."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_hex(value: str | bytes) -> str:
    """Return the hexadecimal SHA-256 of text or bytes."""
    data = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(data).hexdigest()


def canonical_sha256(value: Any) -> str:
    """Return the SHA-256 of the canonical JSON representation."""
    return sha256_hex(canonical_json(value))


def parse_json(value: str) -> Any:
    """Parse JSON with a clear error for corrupted persisted payloads."""
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise ValueError("El contenido persistido no es JSON válido.") from exc
