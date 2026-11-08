"""Extracción de texto de PDF y Markdown."""

import io
import unicodedata
from dataclasses import dataclass

import pypdf
from pypdf import PdfReader

EXTRACTION_VERSION = f"pypdf-{pypdf.__version__}+norm1"
MARKDOWN_VERSION = "markdown+norm1"


class ExtractionError(Exception):
    """El documento no se pudo procesar."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class ExtractedUnit:
    text: str
    page: int | None
    section: str | None
    char_start: int
    char_end: int


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    units: tuple[ExtractedUnit, ...]
    page_count: int | None
    readable_pages: int | None
    unreadable_pages: tuple[int, ...]
    extraction_version: str
    no_usable_text: bool


def normalize_text(text: str) -> str:
    """Normaliza Unicode y espacios sin cambiar el contenido sustantivo."""
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace("\x00", "")
    lines = [line.rstrip() for line in normalized.split("\n")]
    cleaned = "\n".join(lines).strip()
    while "\n\n\n" in cleaned:
        cleaned = cleaned.replace("\n\n\n", "\n\n")
    return cleaned


def extract_pdf(data: bytes) -> ExtractionResult:
    """Extrae texto por página de un PDF textual."""
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = list(reader.pages)
    except Exception as exc:
        raise ExtractionError("invalid_pdf", "El PDF no se pudo leer.") from exc

    if not pages:
        raise ExtractionError("invalid_pdf", "El PDF no contiene páginas.")

    units: list[ExtractedUnit] = []
    unreadable: list[int] = []
    for page_number, page in enumerate(pages, start=1):
        try:
            raw = page.extract_text() or ""
        except Exception:
            raw = ""
        text = normalize_text(raw)
        if text:
            units.append(
                ExtractedUnit(
                    text=text,
                    page=page_number,
                    section=None,
                    char_start=0,
                    char_end=len(text),
                )
            )
        else:
            unreadable.append(page_number)

    return ExtractionResult(
        units=tuple(units),
        page_count=len(pages),
        readable_pages=len(units),
        unreadable_pages=tuple(unreadable),
        extraction_version=EXTRACTION_VERSION,
        no_usable_text=not units,
    )


def _markdown_sections(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    heading = "Introducción"
    buffer: list[str] = []

    def flush() -> None:
        content = normalize_text("\n".join(buffer))
        if content:
            sections.append((heading, content))
        buffer.clear()

    for line in text.splitlines():
        if line.startswith("#"):
            flush()
            heading = line.lstrip("#").strip() or "Sección"
        else:
            buffer.append(line)
    flush()

    if not sections:
        content = normalize_text(text)
        if content:
            sections.append(("Documento", content))
    return sections


def extract_markdown(data: bytes) -> ExtractionResult:
    """Extrae secciones de un Markdown UTF-8."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ExtractionError(
            "invalid_markdown", "El Markdown no está codificado en UTF-8."
        ) from exc

    units: list[ExtractedUnit] = []
    for section, content in _markdown_sections(text):
        units.append(
            ExtractedUnit(
                text=content,
                page=None,
                section=section,
                char_start=0,
                char_end=len(content),
            )
        )

    return ExtractionResult(
        units=tuple(units),
        page_count=None,
        readable_pages=None,
        unreadable_pages=(),
        extraction_version=MARKDOWN_VERSION,
        no_usable_text=not units,
    )


def extract_document(content_type: str, data: bytes) -> ExtractionResult:
    """Despacha la extracción según el tipo detectado."""
    if content_type == "application/pdf":
        return extract_pdf(data)
    if content_type == "text/markdown":
        return extract_markdown(data)
    raise ExtractionError("unsupported_media_type", "Tipo de documento no admitido.")
