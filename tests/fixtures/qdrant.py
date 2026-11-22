"""Constructores de índices Qdrant para pruebas."""

from __future__ import annotations

import hashlib
from pathlib import Path

from qdrant_client import QdrantClient

from secguard_advisor.config import Settings
from secguard_advisor.retrieval.index import QdrantIndex


def embedded_index(path: Path, instance_id: str = "test-local") -> QdrantIndex:
    """Índice Qdrant en modo embebido sobre un directorio temporal."""
    client = QdrantClient(path=str(Path(path) / "qdrant"))
    return QdrantIndex(url="http://127.0.0.1:6333", instance_id=instance_id, client=client)


def _instance_for(settings: Settings) -> str:
    """Instancia estable por almacenamiento.

    Las pruebas de integración usan un `tmp_path` distinto por ejecución. Un ID
    compartido reutilizaría el namespace de Qdrant de una ejecución anterior sin
    el marcador del almacenamiento nuevo, y el índice falla cerrado. Derivar el
    ID de la ruta del almacenamiento conserva el aislamiento sin reutilizar el
    namespace de otra ejecución.
    """
    if settings.instance_id:
        return settings.instance_id
    digest = hashlib.sha256(str(settings.storage_dir.resolve()).encode()).hexdigest()[:10]
    return f"test-{digest}"


def server_index(settings: Settings) -> QdrantIndex:
    """Índice Qdrant contra el servidor configurado (pruebas de integración)."""
    return QdrantIndex(
        url=settings.qdrant_url,
        instance_id=_instance_for(settings),
        timeout=settings.qdrant_timeout_seconds,
        storage_dir=settings.storage_dir,
    )
