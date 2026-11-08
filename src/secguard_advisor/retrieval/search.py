"""Recuperación documental fusionada sobre el corpus público y el caso."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.db.models import Document, DocumentChunk, DocumentVersion
from secguard_advisor.retrieval.collections import case_scope, public_scope


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    """Fragmento recuperado con su procedencia y puntuación."""

    chunk_id: str
    document_id: str
    version_id: str
    document_title: str
    declared_version: str | None
    origin: str
    page: int | None
    section: str | None
    locator: str
    text: str
    score: float
    version_current: bool


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    """Resultado de la recuperación; ``empty`` no prueba ausencia de evidencia."""

    hits: tuple[RetrievedChunk, ...]
    status: str

    @property
    def is_empty(self) -> bool:
        return self.status == "empty"


def _resolve_hit(
    session: Session,
    scope: CaseScope,
    chunk_id: str,
    score: float,
) -> RetrievedChunk | None:
    """Reconstruye el fragmento desde SQLite y descarta lo que ya no es vigente."""
    chunk = session.get(DocumentChunk, chunk_id)
    if chunk is None:
        return None
    version = session.get(DocumentVersion, chunk.version_id)
    if version is None or version.status != "available":
        return None
    document = session.get(Document, version.document_id)
    if document is None:
        return None

    if document.origin == "public_corpus":
        if document.case_id is not None:
            return None
    elif document.case_id != scope.case_id:
        return None

    is_current = document.current_version_id == version.id
    if not is_current:
        return None

    return RetrievedChunk(
        chunk_id=chunk.id,
        document_id=document.id,
        version_id=version.id,
        document_title=document.title,
        declared_version=version.declared_version,
        origin=document.origin,
        page=chunk.page_start,
        section=chunk.section,
        locator=chunk.locator,
        text=chunk.text,
        score=score,
        version_current=is_current,
    )


def search_documents(
    session: Session,
    *,
    scope: CaseScope,
    query: str,
    embedder,
    index,
    top_k: int = 6,
    min_score: float = 0.0,
) -> RetrievalResult:
    """Busca en el corpus público y en las evidencias del caso, sin mezclarlos."""
    embedding = embedder.embed_one(query, kind="query")
    model = embedder.model
    dimension = embedder.dimension

    merged: dict[str, RetrievedChunk] = {}
    for collection_scope in (public_scope(), case_scope(scope.case_id)):
        raw_hits = index.query(
            collection_scope,
            model,
            dimension,
            embedding.vector,
            top_k=top_k,
        )
        for raw in raw_hits:
            score = 1.0 - float(raw.distance)
            if score < min_score:
                continue
            resolved = _resolve_hit(session, scope, raw.chunk_id, score)
            if resolved is None:
                continue
            previous = merged.get(resolved.chunk_id)
            if previous is None or resolved.score > previous.score:
                merged[resolved.chunk_id] = resolved

    ordered = sorted(merged.values(), key=lambda hit: hit.score, reverse=True)
    hits = tuple(ordered[:top_k])
    return RetrievalResult(hits=hits, status="ok" if hits else "empty")
