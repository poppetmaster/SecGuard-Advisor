"""Índice vectorial derivado sobre Chroma."""

from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

import chromadb

from secguard_advisor.retrieval.collections import CollectionScope, collection_name


@dataclass(frozen=True, slots=True)
class IndexedChunk:
    chunk_id: str
    text: str
    embedding: list[float]
    document_id: str
    version_id: str
    origin: str
    source_id: str | None
    page: int | None
    section: str | None
    locator: str


@dataclass(frozen=True, slots=True)
class QueryHit:
    chunk_id: str
    text: str
    metadata: dict
    distance: float


class ChromaIndex:
    """Envoltura mínima del índice, con alcance explícito."""

    def __init__(self, path: Path, client=None) -> None:
        self._client = client or chromadb.PersistentClient(path=str(path))

    def _collection(self, scope: CollectionScope, model: str, dimension: int):
        name = collection_name(scope, model, dimension)
        return self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    def _metadata(self, chunk: IndexedChunk) -> dict:
        return {
            "document_id": chunk.document_id,
            "version_id": chunk.version_id,
            "origin": chunk.origin,
            "source_id": chunk.source_id or "",
            "page": chunk.page or 0,
            "section": chunk.section or "",
            "locator": chunk.locator,
        }

    def upsert(
        self,
        scope: CollectionScope,
        model: str,
        dimension: int,
        chunks: list[IndexedChunk],
    ) -> None:
        if not chunks:
            return
        collection = self._collection(scope, model, dimension)
        collection.upsert(
            ids=[chunk.chunk_id for chunk in chunks],
            embeddings=[chunk.embedding for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            metadatas=[self._metadata(chunk) for chunk in chunks],
        )

    def delete_ids(
        self,
        scope: CollectionScope,
        model: str,
        dimension: int,
        ids: list[str],
    ) -> None:
        if not ids:
            return
        self._collection(scope, model, dimension).delete(ids=ids)

    def delete_version(
        self,
        scope: CollectionScope,
        model: str,
        dimension: int,
        version_id: str,
    ) -> None:
        self._collection(scope, model, dimension).delete(where={"version_id": version_id})

    def count(self, scope: CollectionScope, model: str, dimension: int) -> int:
        return self._collection(scope, model, dimension).count()

    def rebuild(
        self,
        scope: CollectionScope,
        model: str,
        dimension: int,
        chunks: list[IndexedChunk],
    ) -> None:
        name = collection_name(scope, model, dimension)
        with suppress(Exception):
            self._client.delete_collection(name)
        if chunks:
            self.upsert(scope, model, dimension, chunks)

    def query(
        self,
        scope: CollectionScope,
        model: str,
        dimension: int,
        embedding: list[float],
        *,
        top_k: int = 6,
    ) -> list[QueryHit]:
        collection = self._collection(scope, model, dimension)
        result = collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        return [
            QueryHit(
                chunk_id=chunk_id,
                text=document or "",
                metadata=metadata or {},
                distance=float(distance),
            )
            for chunk_id, document, metadata, distance in zip(
                ids, documents, metadatas, distances, strict=False
            )
        ]
