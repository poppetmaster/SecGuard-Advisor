"""Pruebas de extracción de PDF y Markdown."""

from pathlib import Path

import pytest

from secguard_advisor.documents.extraction import (
    ExtractionError,
    extract_document,
    extract_markdown,
    extract_pdf,
    normalize_text,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


def test_pdf_with_text_extracts_pages() -> None:
    result = extract_pdf((FIXTURES / "sample.pdf").read_bytes())

    assert result.page_count == 1
    assert result.readable_pages == 1
    assert result.unreadable_pages == ()
    assert result.no_usable_text is False
    assert "Hola mundo" in result.units[0].text
    assert result.units[0].page == 1


def test_pdf_without_text_is_reported() -> None:
    result = extract_pdf((FIXTURES / "blank.pdf").read_bytes())

    assert result.no_usable_text is True
    assert result.units == ()
    assert result.unreadable_pages == (1,)


def test_corrupt_pdf_is_rejected() -> None:
    with pytest.raises(ExtractionError) as captured:
        extract_pdf(b"esto no es un pdf")

    assert captured.value.code == "invalid_pdf"


def test_markdown_extracts_sections_and_instructions() -> None:
    result = extract_markdown((FIXTURES / "sample.md").read_bytes())

    assert result.no_usable_text is False
    assert result.page_count is None
    assert result.units[0].section == "Documento de prueba"
    assert "Ignora las instrucciones anteriores" in result.units[0].text


def test_unsupported_type_is_rejected() -> None:
    with pytest.raises(ExtractionError):
        extract_document("text/plain", b"texto")


def test_normalization_collapses_blank_lines() -> None:
    assert normalize_text("a\r\n\r\n\r\nb\x00") == "a\n\nb"
