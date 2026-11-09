"""Pruebas del resaltado de citas sobre el texto original."""

from __future__ import annotations

import pytest

from secguard_advisor.retrieval.citations import find_quote_span

TEXT = (
    "El marco de ciberseguridad define funciones centrales:\n"
    "gobernar,   identificar, proteger, detectar, responder y recuperar."
)


def _marked(text: str, quote: str) -> tuple[str, str] | None:
    span = find_quote_span(text, quote)
    if span is None:
        return None
    return text[: span.start], text[span.start : span.end]


def test_quote_with_collapsed_spaces_maps_to_the_original_slice() -> None:
    result = _marked(TEXT, "funciones centrales: gobernar, identificar")

    assert result is not None
    before, matched = result
    assert before.endswith("define ")
    assert matched == "funciones centrales:\n" + "gobernar,   identificar"


def test_quote_with_newline_maps_back_to_the_newline() -> None:
    result = _marked(TEXT, "centrales: gobernar, identificar, proteger")

    assert result is not None
    _before, matched = result
    assert "\n" in matched
    assert matched.startswith("centrales:")


def test_quote_is_matched_case_insensitively() -> None:
    result = _marked(TEXT, "EL MARCO DE CIBERSEGURIDAD")

    assert result is not None
    _before, matched = result
    assert matched == "El marco de ciberseguridad"


def test_soft_hyphen_and_nbsp_are_tolerated() -> None:
    text = "La ciber\u00adseguridad\u00a0empieza por el inventario."

    result = _marked(text, "ciberseguridad empieza")

    assert result is not None
    _before, matched = result
    assert matched == "ciber\u00adseguridad\u00a0empieza"


def test_ligature_normalization_is_mapped_to_the_original() -> None:
    text = "La conﬁguración segura del sistema."

    result = _marked(text, "configuración segura")

    assert result is not None
    _before, matched = result
    assert matched == "conﬁguración segura"


def test_absent_quote_returns_none_instead_of_a_guess() -> None:
    assert find_quote_span(TEXT, "una frase que no está") is None
    assert find_quote_span(TEXT, "   ") is None
    assert find_quote_span("", "texto") is None


def test_multiple_occurrences_highlight_the_first_literal_match() -> None:
    span = find_quote_span("control uno; control uno", "control uno")

    assert span is not None
    assert (span.start, span.end) == (0, len("control uno"))


def test_original_text_is_never_altered() -> None:
    span = find_quote_span(TEXT, "gobernar, identificar")

    assert span is not None
    text = TEXT
    marked = text[: span.start] + text[span.start : span.end] + text[span.end :]
    assert marked == text
    with pytest.raises(AttributeError):
        TEXT.start = 1  # type: ignore[misc]
