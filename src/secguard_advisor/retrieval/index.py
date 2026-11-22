"""Índice vectorial derivado sobre Chroma."""

import uuid
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

import chromadb
from qdrant_client import QdrantClient
from qdrant_client.http import exceptions as qdrant_exceptions
from qdrant_client.models import (
    CreateAlias,
    CreateAliasOperation,
    DeleteAlias,
    DeleteAliasOperation,
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PayloadSchemaType,
    PointIdsList,
    PointStruct,
    VectorParams,
)

from secguard_advisor.retrieval.collections import (
    CollectionScope,
    collection_name,
    instance_alias_name,
    instance_collection_name,
    new_generation_id,
)
from secguard_advisor.retrieval.errors import (
    CaseIndexUnavailable,
    IndexConfigurationError,
    PublicIndexUnavailable,
    QdrantUnavailable,
)
from secguard_advisor.retrieval.instance import InstanceConfigurationError, validate_instance_id


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
    document_title: str | None = None
    declared_version: str | None = None
    chunk_index: int | None = None
    embedding_model: str | None = None
    embedding_dim: int | None = None


@dataclass(frozen=True, slots=True)
class QueryHit:
    chunk_id: str
    text: str
    metadata: dict
    distance: float | None = None
    score: float | None = None


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


# --- Adaptador Qdrant (004, corte 2) ----------------------------------------

SECGUARD_POINT_NAMESPACE = uuid.UUID("6f6d2f10-8f0e-5d4b-9a57-2f6f5f8f1c11")


def point_id(chunk_id: str) -> str:
    """UUIDv5 determinista del `chunk_id`; idempotente entre reconstrucciones."""
    return str(uuid.uuid5(SECGUARD_POINT_NAMESPACE, f"chunk:{chunk_id}"))


def chunk_payload(chunk: IndexedChunk) -> dict:
    """Payload de metadatos; nunca copia el texto del fragmento."""
    payload = {
        "chunk_id": chunk.chunk_id,
        "document_id": chunk.document_id,
        "version_id": chunk.version_id,
        "origin": chunk.origin,
        "source_id": chunk.source_id or "",
        "page_start": chunk.page,
        "section": chunk.section or "",
        "locator": chunk.locator,
    }
    for key, value in (
        ("document_title", chunk.document_title),
        ("declared_version", chunk.declared_version),
        ("chunk_index", chunk.chunk_index),
        ("embedding_model", chunk.embedding_model),
        ("embedding_dim", chunk.embedding_dim),
    ):
        if value is not None:
            payload[key] = value
    return payload


def hit_from_point(point) -> QueryHit:
    payload = dict(point.payload or {})
    return QueryHit(
        chunk_id=str(payload.get("chunk_id", "")),
        text="",
        metadata=payload,
        score=float(point.score),
    )


class QdrantIndex:
    """Índice derivado en Qdrant, resuelto por alias de instancia y alcance."""

    def __init__(
        self,
        *,
        url: str,
        instance_id: str | None,
        timeout: float = 5.0,
        client: QdrantClient | None = None,
    ) -> None:
        try:
            self.instance_id = validate_instance_id(instance_id)
        except InstanceConfigurationError as exc:
            raise IndexConfigurationError(
                "Falta un SECGUARD_INSTANCE_ID válido para resolver el namespace de Qdrant."
            ) from exc
        if not url:
            raise IndexConfigurationError("Falta SECGUARD_QDRANT_URL para conectar con Qdrant.")
        self._url = url
        self._timeout = timeout
        self._client = client

    @property
    def client(self) -> QdrantClient:
        if self._client is None:
            self._client = QdrantClient(url=self._url, timeout=self._timeout)
        return self._client

    def close(self) -> None:
        if self._client is not None:
            with suppress(Exception):
                self._client.close()

    def _unavailable(self, scope: CollectionScope) -> Exception:
        if scope.kind == "case":
            return CaseIndexUnavailable("El índice del caso no está disponible.")
        return PublicIndexUnavailable("El índice público no está disponible.")

    def _alias(self, scope: CollectionScope, model: str, dimension: int) -> str:
        return instance_alias_name(self.instance_id, scope, model, dimension)

    def _resolve(self, scope: CollectionScope, model: str, dimension: int) -> str:
        alias = self._alias(scope, model, dimension)
        try:
            aliases = self.client.get_aliases().aliases
        except Exception as exc:
            raise QdrantUnavailable("No se pudo consultar el índice de Qdrant.") from exc
        for entry in aliases:
            if entry.alias_name == alias:
                return entry.collection_name
        raise self._unavailable(scope)

    def _create_generation(self, scope: CollectionScope, model: str, dimension: int) -> str:
        generation = new_generation_id()
        name = instance_collection_name(self.instance_id, scope, model, dimension, generation)
        try:
            self.client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
            )
            for field in ("document_id", "version_id", "origin"):
                self.client.create_payload_index(
                    collection_name=name,
                    field_name=field,
                    field_schema=PayloadSchemaType.KEYWORD,
                )
        except Exception as exc:
            raise QdrantUnavailable("No se pudo crear la colección de Qdrant.") from exc
        return name

    def _activate_alias(self, alias: str, collection: str) -> None:
        try:
            operations = []
            for entry in self.client.get_aliases().aliases:
                if entry.alias_name == alias:
                    operations.append(
                        DeleteAliasOperation(delete_alias=DeleteAlias(alias_name=alias))
                    )
            operations.append(
                CreateAliasOperation(
                    create_alias=CreateAlias(collection_name=collection, alias_name=alias)
                )
            )
            self.client.update_collection_aliases(change_aliases_operations=operations)
        except Exception as exc:
            raise QdrantUnavailable("No se pudo publicar el alias de Qdrant.") from exc

    def _ensure_collection(self, scope: CollectionScope, model: str, dimension: int) -> str:
        try:
            return self._resolve(scope, model, dimension)
        except CaseIndexUnavailable, PublicIndexUnavailable:
            collection = self._create_generation(scope, model, dimension)
            self._activate_alias(self._alias(scope, model, dimension), collection)
            return collection

    def upsert(
        self,
        scope: CollectionScope,
        model: str,
        dimension: int,
        chunks: list[IndexedChunk],
    ) -> None:
        if not chunks:
            return
        collection = self._ensure_collection(scope, model, dimension)
        points = [
            PointStruct(
                id=point_id(chunk.chunk_id),
                vector=chunk.embedding,
                payload=chunk_payload(chunk),
            )
            for chunk in chunks
        ]
        try:
            self.client.upsert(collection_name=collection, points=points, wait=True)
        except Exception as exc:
            raise QdrantUnavailable("No se pudieron escribir puntos en Qdrant.") from exc

    def delete_ids(
        self,
        scope: CollectionScope,
        model: str,
        dimension: int,
        ids: list[str],
    ) -> None:
        if not ids:
            return
        collection = self._resolve(scope, model, dimension)
        try:
            self.client.delete(
                collection_name=collection,
                points_selector=PointIdsList(points=[point_id(i) for i in ids]),
            )
        except Exception as exc:
            raise QdrantUnavailable("No se pudieron borrar puntos de Qdrant.") from exc

    def delete_version(
        self,
        scope: CollectionScope,
        model: str,
        dimension: int,
        version_id: str,
    ) -> None:
        collection = self._resolve(scope, model, dimension)
        try:
            self.client.delete(
                collection_name=collection,
                points_selector=FilterSelector(
                    filter=Filter(
                        must=[FieldCondition(key="version_id", match=MatchValue(value=version_id))]
                    )
                ),
            )
        except Exception as exc:
            raise QdrantUnavailable("No se pudo borrar la versión de Qdrant.") from exc

    def count(self, scope: CollectionScope, model: str, dimension: int) -> int:
        collection = self._resolve(scope, model, dimension)
        try:
            return int(self.client.count(collection, exact=True).count)
        except Exception as exc:
            raise QdrantUnavailable("No se pudo contar puntos de Qdrant.") from exc

    def query(
        self,
        scope: CollectionScope,
        model: str,
        dimension: int,
        embedding: list[float],
        *,
        top_k: int = 6,
    ) -> list[QueryHit]:
        collection = self._resolve(scope, model, dimension)
        try:
            response = self.client.query_points(
                collection_name=collection,
                query=embedding,
                limit=top_k,
                with_payload=True,
            )
        except qdrant_exceptions.UnexpectedResponse as exc:
            raise QdrantUnavailable("Qdrant rechazó la consulta.") from exc
        except Exception as exc:
            raise QdrantUnavailable("No se pudo consultar Qdrant.") from exc
        return [hit_from_point(point) for point in response.points]
