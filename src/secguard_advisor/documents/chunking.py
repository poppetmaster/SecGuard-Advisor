"""Fragmentación conservadora por página o sección."""

import re
from dataclasses import dataclass

from secguard_advisor.documents.extraction import ExtractedUnit

CHUNKING_VERSION = "chars-4800-overlap-400-v1"
DEFAULT_MAX_CHARS = 4800
DEFAULT_OVERLAP_CHARS = 400


@dataclass(frozen=True, slots=True)
class ChunkCandidate:
    text: str
    page_start: int | None
    page_end: int | None
    section: str | None
    char_start: int
    char_end: int
    locator: str


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "seccion"


def chunk_units(
    units: tuple[ExtractedUnit, ...],
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> list[ChunkCandidate]:
    """Divide unidades en fragmentos sin perder contenido."""
    if max_chars <= 0:
        raise ValueError("max_chars debe ser positivo.")
    if not 0 <= overlap_chars < max_chars:
        raise ValueError("overlap_chars debe ser menor que max_chars.")

    candidates: list[ChunkCandidate] = []
    global_index = 0

    for unit in units:
        text = unit.text
        if not text.strip():
            continue

        start = 0
        while start < len(text):
            end = min(start + max_chars, len(text))
            if end < len(text):
                window = text[start:end]
                boundary = max(window.rfind("\n\n"), window.rfind("\n"), window.rfind(" "))
                if boundary > max_chars // 2:
                    end = start + boundary

            chunk_text = text[start:end].strip()
            if chunk_text:
                if unit.page is not None:
                    locator = f"p:{unit.page}#{global_index}"
                else:
                    locator = f"s:{_slug(unit.section or 'documento')}#{global_index}"
                candidates.append(
                    ChunkCandidate(
                        text=chunk_text,
                        page_start=unit.page,
                        page_end=unit.page,
                        section=unit.section,
                        char_start=start,
                        char_end=end,
                        locator=locator,
                    )
                )
                global_index += 1

            if end >= len(text):
                break
            start = max(end - overlap_chars, start + 1)

    return candidates
