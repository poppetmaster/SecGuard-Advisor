"""Constructores de documentos y fragmentos para pruebas."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from secguard_advisor.db.models import (
    Case,
    Document,
    DocumentChunk,
    DocumentVersion,
    new_id,
    utc_now_iso,
)
from secguard_advisor.documents.validation import sha256_bytes
from secguard_advisor.retrieval.collections import case_scope, public_scope
from secguard_advisor.retrieval.index import IndexedChunk


@dataclass(frozen=True, slots=True)
class SeededDocument:
    document_id: str
    version_id: str
    version_number: int
    chunk_ids: tuple[str, ...]


class NullIndex:
    """Índice inerte para pruebas que no recuperan."""

    def upsert(self, *_args, **_kwargs) -> None:
        return None

    def delete_version(self, *_args, **_kwargs) -> None:
        return None


class NullEmbedder:
    """Embedder inerte con la interfaz mínima."""

    model = "fake-embedding"
    dimension = 4

    def embed_one(self, text: str, *, kind: str = "document", title: str | None = None):
        from secguard_advisor.documents.embedding import EmbeddingResult

        return EmbeddingResult(
            vector=[0.0, 0.0, 0.0, 1.0],
            token_count=1,
            model=self.model,
            dimension=self.dimension,
            prompt=text,
        )

    def close(self) -> None:
        return None


def create_case(session: Session, title: str = "Caso") -> str:
    case = Case(title=title, synthetic_notice="Escenario educativo sintético")
    session.add(case)
    session.flush()
    return case.id


def seed_document(
    factory: sessionmaker[Session],
    *,
    texts: list[str],
    index=None,
    embedder=None,
    case_id: str | None = None,
    source_id: str | None = None,
    title: str = "Documento",
    declared_version: str | None = "v1",
    version_status: str = "available",
    current: bool = True,
    new_version: bool = False,
    pages: list[int | None] | None = None,
    sections: list[str | None] | None = None,
) -> SeededDocument:
    """Crea documento, versión, fragmentos e índice con el mismo contenido."""
    index = index or NullIndex()
    embedder = embedder or NullEmbedder()
    model = getattr(embedder, "model", "fake-embedding")
    dimension = getattr(embedder, "dimension", 4)
    origin = "case_evidence" if case_id else "public_corpus"
    scope_key = f"case:{case_id}" if case_id else f"public:{source_id}"
    resolved_pages = pages or list(range(1, len(texts) + 1))
    resolved_sections = sections or [None] * len(texts)

    with factory() as session:
        document = None
        if new_version:
            if source_id:
                document = session.scalar(
                    select(Document).where(
                        Document.scope_key == scope_key,
                        Document.source_id == source_id,
                    )
                )
            else:
                document = session.scalar(select(Document).where(Document.scope_key == scope_key))
            if document is None:
                raise LookupError("No existe el documento a versionar.")
            if document.current_version_id:
                previous = session.get(DocumentVersion, document.current_version_id)
                if previous is not None:
                    previous.status = "superseded"
                    previous.superseded_at = utc_now_iso()

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
            original_filename=f"{document.id}.md",
            content_type="text/markdown",
            size_bytes=sum(len(text.encode()) for text in texts),
            sha256=sha256_bytes(f"{document.id}:{highest or 0}".encode()),
            declared_version=declared_version,
            status=version_status,
            extraction_version="markdown+norm1",
            normalization_version="norm1",
            chunking_version="chars-4800-overlap-400-v1",
            embedding_model=model,
            embedding_dim=dimension,
        )
        session.add(version)
        session.flush()

        payload: list[IndexedChunk] = []
        chunk_ids: list[str] = []
        for position, text in enumerate(texts):
            chunk_id = new_id()
            locator = f"p:{resolved_pages[position]}#{position}"
            session.add(
                DocumentChunk(
                    id=chunk_id,
                    version_id=version.id,
                    chunk_index=position,
                    page_start=resolved_pages[position],
                    page_end=resolved_pages[position],
                    section=resolved_sections[position],
                    char_start=0,
                    char_end=len(text),
                    text=text,
                    text_sha256=sha256_bytes(text.encode("utf-8")),
                    token_count=10,
                    token_count_source="ollama_prompt_eval_count_single",
                    embedding_model=model,
                    embedding_dim=dimension,
                    index_status="indexed",
                    locator=locator,
                )
            )
            chunk_ids.append(chunk_id)
            result = embedder.embed_one(text, kind="document", title=title)
            payload.append(
                IndexedChunk(
                    chunk_id=chunk_id,
                    text=text,
                    embedding=result.vector,
                    document_id=document.id,
                    version_id=version.id,
                    origin=origin,
                    source_id=source_id,
                    page=resolved_pages[position],
                    section=resolved_sections[position],
                    locator=locator,
                )
            )
        if current:
            document.current_version_id = version.id
        session.commit()
        index.upsert(
            case_scope(case_id) if case_id else public_scope(),
            model,
            dimension,
            payload,
        )
        return SeededDocument(
            document_id=document.id,
            version_id=version.id,
            version_number=version.version_number,
            chunk_ids=tuple(chunk_ids),
        )
