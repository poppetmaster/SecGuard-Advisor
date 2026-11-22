"""Reconstrucción del índice Qdrant desde los fragmentos de SQLite."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from sqlalchemy import select

from secguard_advisor.config import Settings
from secguard_advisor.db.models import Document, DocumentChunk, DocumentVersion
from secguard_advisor.retrieval import instance, status
from secguard_advisor.retrieval.collections import (
    case_scope,
    instance_alias_name,
    public_scope,
)
from secguard_advisor.retrieval.index import IndexedChunk, QdrantIndex


@dataclass(frozen=True, slots=True)
class ScopeReport:
    scope: str
    case_id: str | None
    generation: str | None
    alias: str
    expected_chunks: int
    indexed_chunks: int
    missing_chunks: int
    extra_chunks: int
    previous_missing_chunks: int
    previous_extra_chunks: int
    skipped_chunks: int
    status: str
    error: str | None


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _collect_scopes(factory) -> list[tuple[str, str | None]]:
    scopes: list[tuple[str, str | None]] = []
    with factory() as session:
        public = session.scalar(
            select(Document.id)
            .where(
                Document.origin == "public_corpus",
                Document.current_version_id.is_not(None),
            )
            .limit(1)
        )
        if public is not None:
            scopes.append(("public", None))
        cases = session.scalars(
            select(Document.case_id)
            .where(
                Document.origin == "case_evidence",
                Document.current_version_id.is_not(None),
            )
            .distinct()
            .order_by(Document.case_id)
        ).all()
        scopes.extend(("case", case_id) for case_id in cases if case_id)
    return scopes


def _scope_rows(factory, kind: str, case_id: str | None):
    stmt = (
        select(DocumentChunk, DocumentVersion, Document)
        .join(DocumentVersion, DocumentChunk.version_id == DocumentVersion.id)
        .join(Document, DocumentVersion.document_id == Document.id)
        .where(
            DocumentVersion.status == "available",
            Document.current_version_id == DocumentVersion.id,
        )
    )
    if kind == "public":
        stmt = stmt.where(Document.origin == "public_corpus")
    else:
        stmt = stmt.where(Document.origin == "case_evidence", Document.case_id == case_id)
    stmt = stmt.order_by(Document.id, DocumentChunk.chunk_index)
    with factory() as session:
        return list(session.execute(stmt).all())


def _skip_reason(chunk: DocumentChunk, embedder) -> str | None:
    if not chunk.text.strip():
        return "sin_texto"
    if chunk.embedding_model != embedder.model:
        return "modelo_incompatible"
    if chunk.embedding_dim != embedder.dimension:
        return "dimension_incompatible"
    if not chunk.locator:
        return "sin_localizador"
    return None


def _rebuild_scope(
    factory,
    kind: str,
    case_id: str | None,
    *,
    embedder,
    index: QdrantIndex,
) -> ScopeReport:
    scope = public_scope() if kind == "public" else case_scope(case_id)
    alias = instance_alias_name(index.instance_id, scope, embedder.model, embedder.dimension)
    rows = _scope_rows(factory, kind, case_id)
    generation = None
    try:
        valid: list[IndexedChunk] = []
        skipped = 0
        for chunk, version, document in rows:
            if _skip_reason(chunk, embedder) is not None:
                skipped += 1
                continue
            result = embedder.embed_one(chunk.text, kind="document", title=document.title)
            valid.append(
                IndexedChunk(
                    chunk_id=chunk.id,
                    text=chunk.text,
                    embedding=result.vector,
                    document_id=document.id,
                    version_id=version.id,
                    origin=document.origin,
                    source_id=document.source_id,
                    page=chunk.page_start,
                    section=chunk.section,
                    locator=chunk.locator,
                    document_title=document.title,
                    declared_version=version.declared_version,
                    chunk_index=chunk.chunk_index,
                    embedding_model=chunk.embedding_model,
                    embedding_dim=chunk.embedding_dim,
                )
            )

        expected = {item.chunk_id for item in valid}
        previous_collection = index.active_collection(scope, embedder.model, embedder.dimension)
        previous = index.chunk_ids(previous_collection) if previous_collection else set()

        if rows:
            generation, collection = index.create_generation(
                scope, embedder.model, embedder.dimension
            )
            index.upsert_to(collection, valid)
            found = index.chunk_ids(collection)
        else:
            collection = ""
            found = set()

        # La candidata se valida solo contra SQLite. Las discrepancias de la
        # generación anterior son diagnóstico y no impiden publicar una
        # candidata completa: el índice anterior puede estar desactualizado.
        missing = expected - found
        extra = found - expected
        previous_missing = expected - previous
        previous_extra = previous - expected
        complete = not missing and not extra and skipped == 0
        if complete and collection:
            index.activate_alias(scope, embedder.model, embedder.dimension, collection)

        return ScopeReport(
            scope=kind,
            case_id=case_id,
            generation=generation,
            alias=alias,
            expected_chunks=len(expected),
            indexed_chunks=len(found),
            missing_chunks=len(missing),
            extra_chunks=len(extra),
            previous_missing_chunks=len(previous_missing),
            previous_extra_chunks=len(previous_extra),
            skipped_chunks=skipped,
            status="completed" if complete else "partial",
            error=None,
        )
    except Exception as exc:
        return ScopeReport(
            scope=kind,
            case_id=case_id,
            generation=generation,
            alias=alias,
            expected_chunks=len(rows),
            indexed_chunks=0,
            missing_chunks=len(rows),
            extra_chunks=0,
            previous_missing_chunks=0,
            previous_extra_chunks=0,
            skipped_chunks=0,
            status="failed",
            error=type(exc).__name__,
        )


def _write_report(settings: Settings, instance_id: str, report: dict) -> None:
    target = status.reports_dir(settings.storage_dir, instance_id)
    target.mkdir(parents=True, exist_ok=True)
    stamp = report["started_at"].replace("-", "").replace(":", "")
    body = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    (target / f"rebuild-{stamp}.json").write_text(body, encoding="utf-8")
    temporary = target / "latest.json.tmp"
    temporary.write_text(body, encoding="utf-8")
    os.replace(temporary, target / "latest.json")


def rebuild(
    factory,
    settings: Settings,
    *,
    embedder,
    index: QdrantIndex,
) -> dict:
    instance_id = instance.validate_instance_id(settings.instance_id)
    started = _utc_now()
    scopes: list[ScopeReport] = []
    # El reporte terminal se construye y publica dentro del lock: una ejecución
    # anterior no puede sobrescribir latest.json después de otra operación. El
    # context manager libera el lock incluso si la escritura del reporte falla.
    with instance.acquire_instance_lock(settings.storage_dir, instance_id, "rebuild"):
        for kind, case_id in _collect_scopes(factory):
            scopes.append(_rebuild_scope(factory, kind, case_id, embedder=embedder, index=index))
        report = {
            "started_at": started,
            "finished_at": _utc_now(),
            "status": status.terminal_status([item.status for item in scopes]),
            "backend": "qdrant",
            "embedding_model": embedder.model,
            "embedding_dim": embedder.dimension,
            "scopes": [asdict(item) for item in scopes],
        }
        _write_report(settings, instance_id, report)
    return report
