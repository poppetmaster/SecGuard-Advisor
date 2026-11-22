"""Constructores de índices Qdrant para pruebas."""

from __future__ import annotations

from pathlib import Path

from qdrant_client import QdrantClient

from secguard_advisor.config import Settings
from secguard_advisor.retrieval.index import QdrantIndex


def embedded_index(path: Path, instance_id: str = "test-local") -> QdrantIndex:
    """Índice Qdrant en modo embebido sobre un directorio temporal."""
    client = QdrantClient(path=str(Path(path) / "qdrant"))
    return QdrantIndex(url="http://127.0.0.1:6333", instance_id=instance_id, client=client)


def server_index(settings: Settings) -> QdrantIndex:
    """Índice Qdrant contra el servidor configurado (pruebas de integración)."""
    return QdrantIndex(
        url=settings.qdrant_url,
        instance_id=settings.instance_id or "test-integration",
        timeout=settings.qdrant_timeout_seconds,
        storage_dir=settings.storage_dir,
    )
