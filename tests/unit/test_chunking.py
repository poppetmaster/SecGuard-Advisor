"""Pruebas de fragmentación."""

from secguard_advisor.documents.chunking import (
    DEFAULT_MAX_CHARS,
    chunk_units,
)
from secguard_advisor.documents.extraction import ExtractedUnit


def _unit(text: str, page: int | None, section: str | None = None) -> ExtractedUnit:
    return ExtractedUnit(
        text=text,
        page=page,
        section=section,
        char_start=0,
        char_end=len(text),
    )


def test_long_text_is_split_within_budget() -> None:
    text = ("parrafo de prueba " * 900).strip()
    units = (_unit(text, page=3),)

    chunks = chunk_units(units)

    assert len(chunks) > 1
    assert all(len(chunk.text) <= DEFAULT_MAX_CHARS for chunk in chunks)
    assert chunks[0].page_start == 3
    assert chunks[-1].page_end == 3
    assert chunks[-1].char_end == len(text)


def test_chunks_overlap_within_the_same_unit() -> None:
    text = ("contenido " * 1200).strip()
    chunks = chunk_units((_unit(text, page=1),), max_chars=600, overlap_chars=50)

    assert len(chunks) > 1
    assert chunks[1].char_start < chunks[0].char_end


def test_section_and_page_are_preserved() -> None:
    text = "Contenido de la sección con instrucciones incrustadas."
    chunks = chunk_units((_unit(text, page=None, section="Documento de prueba"),))

    assert chunks[0].section == "Documento de prueba"
    assert chunks[0].page_start is None
    assert chunks[0].locator.startswith("s:documento-de-prueba#")


def test_short_text_produces_one_chunk() -> None:
    chunks = chunk_units((_unit("texto corto", page=1),))

    assert len(chunks) == 1
    assert chunks[0].text == "texto corto"
    assert chunks[0].locator == "p:1#0"
