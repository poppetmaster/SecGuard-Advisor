"""Validación del parseo estructurado común a los adaptadores API."""

from __future__ import annotations

import pytest

from secguard_advisor.conversation.llm import InvalidModelOutput, ToolDecision
from secguard_advisor.conversation.providers.http_common import parse_structured


def test_parse_structured_accepts_plain_json() -> None:
    decision = parse_structured(
        '{"use_findings": true, "arguments": {"severity": "High"}}',
        ToolDecision,
    )

    assert decision.use_findings is True


def test_parse_structured_accepts_json_inside_a_code_fence() -> None:
    content = '```json\n{"use_findings": false, "arguments": {}}\n```'

    decision = parse_structured(content, ToolDecision)

    assert decision.use_findings is False


def test_parse_structured_ignores_surrounding_prose() -> None:
    content = 'Aquí está la decisión:\n{"use_findings": false}\nFin.'

    decision = parse_structured(content, ToolDecision)

    assert decision.use_findings is False


def test_parse_structured_rejects_invalid_json() -> None:
    with pytest.raises(InvalidModelOutput):
        parse_structured("no es json", ToolDecision)


def test_parse_structured_rejects_a_schema_mismatch() -> None:
    with pytest.raises(InvalidModelOutput):
        parse_structured('{"use_findings": "quizá"}', ToolDecision)
