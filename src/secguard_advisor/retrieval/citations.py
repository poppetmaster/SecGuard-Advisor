"""Control automático de citas: existencia, localización y cita literal."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from sqlalchemy.orm import Session

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.db.models import Document, DocumentChunk, DocumentVersion

MAX_QUOTE_CHARS = 400


@dataclass(frozen=True, slots=True)
class CitationCheck:
    """Resultado del control 1 sobre una cita."""

    status: str
    reason: str | None
    chunk: DocumentChunk | None = None
    version: DocumentVersion | None = None
    document: Document | None = None

    @property
    def valid(self) -> bool:
        return self.status == "valid"


def normalize_for_match(text: str) -> str:
    """Normaliza texto para comparar citas literales sin alterar el contenido."""
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.replace("\u00ad", "")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip().casefold()


@dataclass(frozen=True, slots=True)
class QuoteSpan:
    """Tramo del texto original que corresponde a la cita normalizada."""

    start: int
    end: int


def _fold_char(char: str) -> str:
    return unicodedata.normalize("NFKC", char).casefold()


def find_quote_span(text: str, quote: str) -> QuoteSpan | None:
    """Localiza la cita normalizada y devuelve su tramo en el texto original.

    Construye una cadena normalizada con un índice hacia el carácter original de
    cada posición. Si la cita no aparece o el tramo original no vuelve a
    normalizarse igual, devuelve ``None`` para no resaltar algo engañoso.
    """
    cleaned = (quote or "").strip()
    if not cleaned or not text:
        return None

    folded_chars: list[str] = []
    source_indices: list[int] = []
    previous_space = True
    for index, char in enumerate(text):
        if char == "\u00ad":
            continue
        folded = _fold_char(char)
        if not folded:
            continue
        if folded.isspace():
            if previous_space:
                continue
            folded_chars.append(" ")
            source_indices.append(index)
            previous_space = True
            continue
        for out_char in folded:
            folded_chars.append(out_char)
            source_indices.append(index)
        previous_space = False

    while folded_chars and folded_chars[-1] == " ":
        folded_chars.pop()
        source_indices.pop()

    needle = normalize_for_match(cleaned)
    haystack = "".join(folded_chars)
    position = haystack.find(needle)
    if position < 0:
        return None

    end_position = position + len(needle)
    start = source_indices[position]
    end = source_indices[end_position - 1] + 1
    if normalize_for_match(text[start:end]) != needle:
        return None
    return QuoteSpan(start=start, end=end)


def _rejected(reason: str, **kwargs) -> CitationCheck:
    return CitationCheck(status="rejected", reason=reason, **kwargs)


def check_citation(
    session: Session,
    scope: CaseScope,
    *,
    chunk_id: str,
    version_id: str,
    page: int | None,
    section: str | None,
    quote: str,
) -> CitationCheck:
    """Verifica que la cita resuelva a un fragmento autorizado y contenga su texto."""
    cleaned = (quote or "").strip()
    if not cleaned:
        return _rejected("quote_empty")
    if len(cleaned) > MAX_QUOTE_CHARS:
        return _rejected("quote_too_long")

    chunk = session.get(DocumentChunk, chunk_id)
    if chunk is None:
        return _rejected("chunk_missing")
    if chunk.version_id != version_id:
        return _rejected("version_mismatch", chunk=chunk)

    version = session.get(DocumentVersion, chunk.version_id)
    if version is None:
        return _rejected("chunk_missing", chunk=chunk)
    document = session.get(Document, version.document_id)
    if document is None:
        return _rejected("chunk_missing", chunk=chunk, version=version)

    if document.origin == "public_corpus":
        if document.case_id is not None:
            return _rejected("scope_mismatch", chunk=chunk, version=version, document=document)
    elif document.case_id != scope.case_id:
        return _rejected("scope_mismatch", chunk=chunk, version=version, document=document)

    if page is not None:
        low = chunk.page_start if chunk.page_start is not None else chunk.page_end
        high = chunk.page_end if chunk.page_end is not None else chunk.page_start
        if low is None or high is None or not low <= page <= high:
            return _rejected("page_mismatch", chunk=chunk, version=version, document=document)
    if section is not None and normalize_for_match(section) != normalize_for_match(
        chunk.section or ""
    ):
        return _rejected("section_mismatch", chunk=chunk, version=version, document=document)

    if normalize_for_match(cleaned) not in normalize_for_match(chunk.text):
        return _rejected("quote_not_found", chunk=chunk, version=version, document=document)

    return CitationCheck(
        status="valid",
        reason=None,
        chunk=chunk,
        version=version,
        document=document,
    )
