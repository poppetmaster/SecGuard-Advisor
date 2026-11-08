"""Orquestación de ingesta de documentos."""

import json
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session, sessionmaker

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.db.models import (
    Document,
    DocumentChunk,
    DocumentVersion,
    IngestionJob,
    new_id,
    utc_now_iso,
)
from secguard_advisor.documents.chunking import (
    CHUNKING_VERSION,
    ChunkCandidate,
    chunk_units,
)
from secguard_advisor.documents.embedding import (
    EmbeddingError,
    EmbeddingResult,
    EmbeddingTooLong,
)
from secguard_advisor.documents.extraction import (
    ExtractionError,
    extract_document,
)
from secguard_advisor.documents.storage import read_original, store_original
from secguard_advisor.documents.validation import UploadedContent, sha256_bytes
from secguard_advisor.retrieval.collections import case_scope, public_scope
from secguard_advisor.retrieval.index import IndexedChunk


class DocumentNotFound(LookupError):
    """El documento no existe en el alcance autorizado."""


class DocumentConflict(RuntimeError):
    """El documento no admite la operación solicitada."""


class EmbedderProtocol(Protocol):
    model: str
    dimension: int

    def embed_one(
        self,
        text: str,
        *,
        kind: str = "document",
        title: str | None = None,
    ) -> EmbeddingResult: ...

    def close(self) -> None: ...


class IndexProtocol(Protocol):
    def upsert(self, scope, model: str, dimension: int, chunks: list[IndexedChunk]) -> None: ...

    def delete_version(self, scope, model: str, dimension: int, version_id: str) -> None: ...


@dataclass(frozen=True, slots=True)
class IngestionOutcome:
    status: str
    document_id: str
    version_id: str
    version_number: int
    chunks: int
    message: str


def _scope_for(case_id: str | None, source_id: str | None):
    if case_id is not None:
        return case_scope(case_id)
    if source_id is not None:
        return public_scope()
    raise ValueError("El documento debe tener caso o fuente pública.")


def _finish_failed(
    factory: sessionmaker[Session],
    version_id: str,
    job_id: str,
    code: str,
    message: str,
) -> IngestionOutcome:
    with factory() as session:
        version = session.get(DocumentVersion, version_id)
        job = session.get(IngestionJob, job_id)
        if version is not None:
            version.status = "failed"
            version.error_code = code
            version.error_message = message
        if job is not None:
            job.status = "failed"
            job.finished_at = utc_now_iso()
            job.error_code = code
            job.error_message = message
        session.commit()
        return IngestionOutcome(
            status="failed",
            document_id=version.document_id if version else "",
            version_id=version_id,
            version_number=version.version_number if version else 0,
            chunks=0,
            message=message,
        )


def _finish_no_text(
    factory: sessionmaker[Session],
    version_id: str,
    job_id: str,
    extraction,
) -> IngestionOutcome:
    message = (
        "El documento no contiene texto utilizable. "
        "Si es un PDF escaneado, se requiere OCR, que no forma parte de este incremento."
    )
    with factory() as session:
        version = session.get(DocumentVersion, version_id)
        job = session.get(IngestionJob, job_id)
        if version is not None:
            version.status = "no_usable_text"
            version.error_code = "no_usable_text"
            version.error_message = message
            version.page_count = extraction.page_count
            version.readable_pages = extraction.readable_pages
            version.unreadable_pages = json.dumps(list(extraction.unreadable_pages))
            version.extraction_version = extraction.extraction_version
        if job is not None:
            job.status = "failed"
            job.finished_at = utc_now_iso()
            job.error_code = "no_usable_text"
            job.error_message = message
        session.commit()
        return IngestionOutcome(
            status="no_usable_text",
            document_id=version.document_id if version else "",
            version_id=version_id,
            version_number=version.version_number if version else 0,
            chunks=0,
            message=message,
        )


def _split_candidate(candidate: ChunkCandidate) -> tuple[ChunkCandidate, ChunkCandidate]:
    text = candidate.text
    middle = len(text) // 2
    split_at = text.rfind(" ", 0, middle)
    if split_at <= 0:
        split_at = text.find(" ", middle)
    if split_at <= 0 or split_at >= len(text) - 1:
        split_at = middle
    left_text = text[:split_at].strip()
    right_text = text[split_at:].strip()
    if not left_text or not right_text:
        raise EmbeddingTooLong("El fragmento no se puede dividir más.")

    def build(part: str, offset: int) -> ChunkCandidate:
        start = candidate.char_start + offset
        return ChunkCandidate(
            text=part,
            page_start=candidate.page_start,
            page_end=candidate.page_end,
            section=candidate.section,
            char_start=start,
            char_end=start + len(part),
            locator=candidate.locator,
        )

    return (
        build(left_text, 0),
        build(right_text, len(text) - len(right_text)),
    )


def _embed_candidates(
    embedder: EmbedderProtocol,
    candidates: list[ChunkCandidate],
    title: str,
) -> list[tuple[ChunkCandidate, EmbeddingResult]]:
    pending = list(candidates)
    embedded: list[tuple[ChunkCandidate, EmbeddingResult]] = []
    splits = 0

    while pending:
        candidate = pending.pop(0)
        try:
            result = embedder.embed_one(candidate.text, kind="document", title=title)
        except EmbeddingTooLong:
            splits += 1
            if splits > 20:
                raise
            left, right = _split_candidate(candidate)
            pending[0:0] = [left, right]
            continue
        embedded.append((candidate, result))

    return embedded


def _persist_chunks(
    factory: sessionmaker[Session],
    version_id: str,
    embedder: EmbedderProtocol,
    embedded: list[tuple[ChunkCandidate, EmbeddingResult]],
    *,
    origin: str,
    source_id: str | None,
) -> list[IndexedChunk]:
    with factory() as session:
        version = session.get(DocumentVersion, version_id)
        if version is None:
            raise DocumentNotFound(version_id)
        session.execute(delete(DocumentChunk).where(DocumentChunk.version_id == version_id))
        payload: list[IndexedChunk] = []
        for index, (candidate, result) in enumerate(embedded):
            chunk_id = new_id()
            session.add(
                DocumentChunk(
                    id=chunk_id,
                    version_id=version_id,
                    chunk_index=index,
                    page_start=candidate.page_start,
                    page_end=candidate.page_end,
                    section=candidate.section,
                    char_start=candidate.char_start,
                    char_end=candidate.char_end,
                    text=candidate.text,
                    text_sha256=sha256_bytes(candidate.text.encode("utf-8")),
                    token_count=result.token_count,
                    token_count_source="ollama_prompt_eval_count_single",
                    embedding_model=embedder.model,
                    embedding_dim=embedder.dimension,
                    index_status="pending",
                    locator=candidate.locator,
                )
            )
            payload.append(
                IndexedChunk(
                    chunk_id=chunk_id,
                    text=candidate.text,
                    embedding=result.vector,
                    document_id=version.document_id,
                    version_id=version_id,
                    origin=origin,
                    source_id=source_id,
                    page=candidate.page_start,
                    section=candidate.section,
                    locator=candidate.locator,
                )
            )
        session.commit()
        return payload


def _process_version(
    factory: sessionmaker[Session],
    settings: Settings,
    *,
    version_id: str,
    job_id: str,
    document_id: str,
    upload: UploadedContent,
    title: str,
    case_id: str | None,
    source_id: str | None,
    origin: str,
    embedder: EmbedderProtocol,
    index: IndexProtocol,
) -> IngestionOutcome:
    try:
        extraction = extract_document(upload.content_type, upload.data)
    except ExtractionError as exc:
        return _finish_failed(factory, version_id, job_id, exc.code, exc.message)

    if extraction.no_usable_text:
        return _finish_no_text(factory, version_id, job_id, extraction)

    candidates = chunk_units(extraction.units)
    if not candidates:
        return _finish_no_text(factory, version_id, job_id, extraction)

    try:
        embedded = _embed_candidates(embedder, candidates, title)
    except EmbeddingTooLong:
        return _finish_failed(
            factory,
            version_id,
            job_id,
            "embedding_too_long",
            "Un fragmento excede el contexto del modelo de embeddings.",
        )
    except EmbeddingError as exc:
        return _finish_failed(factory, version_id, job_id, "embedding_failed", str(exc))

    scope = _scope_for(case_id, source_id)
    with suppress(Exception):
        index.delete_version(scope, embedder.model, embedder.dimension, version_id)

    try:
        payload = _persist_chunks(
            factory,
            version_id,
            embedder,
            embedded,
            origin=origin,
            source_id=source_id,
        )
        index.upsert(scope, embedder.model, embedder.dimension, payload)
    except Exception:
        return _finish_failed(
            factory,
            version_id,
            job_id,
            "index_failed",
            "No se pudo indexar el documento.",
        )

    now = utc_now_iso()
    with factory() as session:
        version = session.get(DocumentVersion, version_id)
        document = session.get(Document, document_id)
        job = session.get(IngestionJob, job_id)
        if version is None or document is None or job is None:
            raise DocumentNotFound(version_id)

        previous_id = document.current_version_id
        if previous_id and previous_id != version_id:
            previous = session.get(DocumentVersion, previous_id)
            if previous is not None:
                previous.status = "superseded"
                previous.superseded_at = now

        version.status = "available"
        version.error_code = None
        version.error_message = None
        version.page_count = extraction.page_count
        version.readable_pages = extraction.readable_pages
        version.unreadable_pages = json.dumps(list(extraction.unreadable_pages))
        version.extraction_version = extraction.extraction_version
        version.chunking_version = CHUNKING_VERSION
        version.embedding_model = embedder.model
        version.embedding_dim = embedder.dimension
        document.current_version_id = version_id
        job.status = "succeeded"
        job.finished_at = now
        job.error_code = None
        job.error_message = None
        session.execute(
            update(DocumentChunk)
            .where(DocumentChunk.version_id == version_id)
            .values(index_status="indexed", index_error=None)
        )
        session.commit()

        return IngestionOutcome(
            status="created",
            document_id=document_id,
            version_id=version_id,
            version_number=version.version_number,
            chunks=len(payload),
            message="Documento disponible para consulta.",
        )


def ingest_document(
    factory: sessionmaker[Session],
    settings: Settings,
    *,
    scope_key: str,
    case_id: str | None,
    origin: str,
    source_id: str | None,
    title: str,
    upload: UploadedContent,
    embedder: EmbedderProtocol,
    index: IndexProtocol,
    declared_version: str | None = None,
    declared_date: str | None = None,
    retrieved_at: str | None = None,
    license: str | None = None,
    store_original_file: bool = True,
) -> IngestionOutcome:
    """Crea una versión y la procesa sin duplicar contenido."""
    if store_original_file:
        store_original(settings, upload)

    with factory() as session:
        existing = session.scalar(
            select(DocumentVersion).where(
                DocumentVersion.scope_key == scope_key,
                DocumentVersion.sha256 == upload.sha256,
            )
        )
        if existing is not None:
            document = session.get(Document, existing.document_id)
            return IngestionOutcome(
                status="duplicate",
                document_id=document.id if document else "",
                version_id=existing.id,
                version_number=existing.version_number,
                chunks=0,
                message="El contenido ya existe en este alcance.",
            )

        if origin == "public_corpus":
            document = session.scalar(
                select(Document).where(
                    Document.scope_key == scope_key,
                    Document.source_id == source_id,
                )
            )
        else:
            document = session.scalar(
                select(Document)
                .join(
                    DocumentVersion,
                    DocumentVersion.document_id == Document.id,
                )
                .where(
                    Document.scope_key == scope_key,
                    DocumentVersion.original_filename == upload.filename,
                )
                .order_by(DocumentVersion.version_number.desc())
            )

        if document is None:
            document = Document(
                scope_key=scope_key,
                case_id=case_id,
                origin=origin,
                source_id=source_id,
                title=title,
            )
            session.add(document)
            session.flush()

        highest = session.scalar(
            select(func.max(DocumentVersion.version_number)).where(
                DocumentVersion.document_id == document.id
            )
        )
        version = DocumentVersion(
            document_id=document.id,
            scope_key=scope_key,
            version_number=(highest or 0) + 1,
            original_filename=upload.filename,
            content_type=upload.content_type,
            size_bytes=upload.size,
            sha256=upload.sha256,
            declared_version=declared_version,
            declared_date=declared_date,
            status="processing",
            extraction_version="pending",
            normalization_version="norm1",
            chunking_version=CHUNKING_VERSION,
            embedding_model=embedder.model,
            embedding_dim=embedder.dimension,
            retrieved_at=retrieved_at,
            license=license,
        )
        session.add(version)
        session.flush()

        job = IngestionJob(
            id=new_id(),
            case_id=case_id,
            version_id=version.id,
            status="running",
            attempts=1,
            started_at=utc_now_iso(),
            heartbeat_at=utc_now_iso(),
        )
        session.add(job)
        session.commit()

        document_id = document.id
        version_id = version.id
        job_id = job.id
        resolved_title = document.title

    return _process_version(
        factory,
        settings,
        version_id=version_id,
        job_id=job_id,
        document_id=document_id,
        upload=upload,
        title=resolved_title,
        case_id=case_id,
        source_id=source_id,
        origin=origin,
        embedder=embedder,
        index=index,
    )


def list_documents(session: Session, case_id: str) -> list[Document]:
    return list(
        session.scalars(
            select(Document)
            .where(Document.case_id == case_id, Document.origin == "case_evidence")
            .order_by(Document.created_at.desc())
        )
    )


def get_document(session: Session, scope: CaseScope, document_id: str) -> Document:
    document = session.get(Document, document_id)
    if document is None or document.case_id != scope.case_id or document.origin != "case_evidence":
        raise DocumentNotFound(document_id)
    return document


def list_versions(session: Session, document_id: str) -> list[DocumentVersion]:
    return list(
        session.scalars(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc())
        )
    )


def list_chunks(session: Session, version_id: str) -> list[DocumentChunk]:
    return list(
        session.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.version_id == version_id)
            .order_by(DocumentChunk.chunk_index.asc())
        )
    )


def retry_ingestion(
    factory: sessionmaker[Session],
    settings: Settings,
    *,
    scope: CaseScope,
    document_id: str,
    embedder: EmbedderProtocol,
    index: IndexProtocol,
) -> IngestionOutcome:
    """Reintenta la última versión fallida de un documento."""
    with factory() as session:
        document = get_document(session, scope, document_id)
        latest = session.scalar(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document.id)
            .order_by(DocumentVersion.version_number.desc())
        )
        if latest is None:
            raise DocumentNotFound(document_id)
        if latest.status in {"available", "processing"}:
            raise DocumentConflict("La versión más reciente no admite reintento.")
        extension = Path(latest.original_filename).suffix.lower()
        try:
            data = read_original(settings, latest.sha256, extension)
        except FileNotFoundError:
            return _finish_failed(
                factory,
                latest.id,
                new_id(),
                "original_missing",
                "No se encontró el original para reintentar la ingesta.",
            )

        attempts = (
            session.scalar(
                select(func.max(IngestionJob.attempts)).where(IngestionJob.version_id == latest.id)
            )
            or 0
        )
        latest.status = "processing"
        latest.error_code = None
        latest.error_message = None
        job = IngestionJob(
            id=new_id(),
            case_id=document.case_id,
            version_id=latest.id,
            status="running",
            attempts=attempts + 1,
            started_at=utc_now_iso(),
            heartbeat_at=utc_now_iso(),
        )
        session.add(job)
        session.commit()
        version_id = latest.id
        job_id = job.id
        title = document.title
        upload = UploadedContent(
            filename=latest.original_filename,
            content_type=latest.content_type,
            data=data,
            sha256=latest.sha256,
            size=len(data),
            extension=extension,
        )

    return _process_version(
        factory,
        settings,
        version_id=version_id,
        job_id=job_id,
        document_id=document_id,
        upload=upload,
        title=title,
        case_id=scope.case_id,
        source_id=None,
        origin="case_evidence",
        embedder=embedder,
        index=index,
    )


@dataclass(frozen=True, slots=True)
class DocumentOverview:
    id: str
    title: str
    created_at: str
    status: str
    current_status: str | None
    version_id: str | None
    version_number: int | None
    chunks: int


def documents_overview(session: Session, case_id: str) -> list[DocumentOverview]:
    """Resumen de documentos y su versión vigente o última."""
    overview: list[DocumentOverview] = []
    for document in list_documents(session, case_id):
        latest = session.scalar(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document.id)
            .order_by(DocumentVersion.version_number.desc())
        )
        current = (
            session.get(DocumentVersion, document.current_version_id)
            if document.current_version_id
            else None
        )
        version = current or latest
        chunks = (
            session.scalar(
                select(func.count())
                .select_from(DocumentChunk)
                .where(DocumentChunk.version_id == version.id)
            )
            if version is not None
            else 0
        )
        overview.append(
            DocumentOverview(
                id=document.id,
                title=document.title,
                created_at=document.created_at,
                status=latest.status if latest is not None else "pending",
                current_status=current.status if current is not None else None,
                version_id=version.id if version is not None else None,
                version_number=version.version_number if version is not None else None,
                chunks=chunks or 0,
            )
        )
    return overview
