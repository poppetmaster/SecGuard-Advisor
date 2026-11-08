"""Almacenamiento content-addressed de originales."""

import re
from pathlib import Path

from secguard_advisor.config import Settings
from secguard_advisor.documents.validation import UploadedContent

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _safe_sha(sha256: str) -> str:
    if not _SHA256.match(sha256):
        raise ValueError("Hash SHA-256 inválido.")
    return sha256


def original_path(settings: Settings, sha256: str, extension: str) -> Path:
    """Ruta content-addressed dentro del almacenamiento controlado."""
    safe = _safe_sha(sha256)
    path = (settings.originals_dir / safe[:2] / f"{safe}{extension}").resolve()
    root = settings.originals_dir.resolve()
    if not path.is_relative_to(root):
        raise ValueError("La ruta del original queda fuera del almacenamiento.")
    return path


def store_original(settings: Settings, content: UploadedContent) -> Path:
    """Guarda el original de forma idempotente."""
    path = original_path(settings, content.sha256, content.extension)
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_bytes(content.data)
    temporary.replace(path)
    return path


def read_original(settings: Settings, sha256: str, extension: str) -> bytes:
    """Lee un original ya almacenado."""
    path = original_path(settings, sha256, extension)
    if not path.exists():
        raise FileNotFoundError(path)
    return path.read_bytes()
