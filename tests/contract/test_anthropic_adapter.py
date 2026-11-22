"""Contrato del adaptador Anthropic con transporte simulado."""

from __future__ import annotations

import json

import httpx
import pytest

from secguard_advisor.config import Settings
from secguard_advisor.conversation.llm import AnswerPayload, InvalidModelOutput, ToolDecision
from secguard_advisor.conversation.providers.anthropic import AnthropicGenerator
from secguard_advisor.conversation.providers.base import ProviderAuthError


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        generation_provider="anthropic",
        generation_model="claude-haiku-5-5",
        generation_max_output_tokens=64,
        anthropic_api_key="sk-ant-secret",
        anthropic_base_url="https://anthropic.test",
        anthropic_version="2026-10-21",
    )


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_generate_uses_structured_outputs_and_records_usage() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["key"] = request.headers["x-api-key"]
        seen["version"] = request.headers["anthropic-version"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "claude-haiku-5-5",
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "answer": "La restauración se prueba trimestralmente.",
                                "claims": [],
                                "missing_info": [],
                                "recommendations": [],
                            }
                        ),
                    }
                ],
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 20,
                    "cache_read_input_tokens": 10,
                    "cache_creation_input_tokens": 0,
                },
            },
        )

    generator = AnthropicGenerator(_settings(), client=_client(handler))
    try:
        payload = generator.generate(system="Respondé.", user="¿Cada cuánto?")
    finally:
        generator.close()

    assert isinstance(payload, AnswerPayload)
    assert seen["path"] == "/v1/messages"
    assert seen["key"] == "sk-ant-secret"
    assert seen["version"] == "2026-10-21"
    assert seen["body"]["max_tokens"] == 64
    assert "temperature" not in seen["body"]
    assert seen["body"]["output_config"]["format"]["type"] == "json_schema"
    assert "sk-ant-secret" not in repr(seen["body"])
    assert generator.identity == "claude-haiku-5-5"
    assert generator.last_usage["input_tokens"] == 100
    assert generator.last_usage["cached_tokens"] == 10


def test_decide_returns_a_validated_tool_decision() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "claude-haiku-5-5",
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "use_findings": True,
                                "arguments": {
                                    "origin": "synthetic",
                                    "severity": "High",
                                },
                            }
                        ),
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        )

    generator = AnthropicGenerator(_settings(), client=_client(handler))
    try:
        decision = generator.decide(system="Clasificá.", user="¿High?")
    finally:
        generator.close()

    assert isinstance(decision, ToolDecision)
    assert decision.use_findings is True
    assert decision.arguments.severity == "High"


def test_invalid_json_is_rejected() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "no es json"}],
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    generator = AnthropicGenerator(_settings(), client=_client(handler))
    try:
        with pytest.raises(InvalidModelOutput):
            generator.generate(system="Respondé.", user="¿Qué?")
    finally:
        generator.close()


def test_auth_error_is_normalized_without_leaking_the_key() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "sk-ant-secret"})

    generator = AnthropicGenerator(_settings(), client=_client(handler))
    try:
        with pytest.raises(ProviderAuthError) as captured:
            generator.generate(system="Respondé.", user="¿Qué?")
    finally:
        generator.close()

    assert "sk-ant-secret" not in str(captured.value)


def test_per_call_timeout_reaches_the_transport() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["timeout"] = request.extensions.get("timeout")
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "{}"}],
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), timeout=12.5)
    generator = AnthropicGenerator(_settings(), client=client)
    try:
        with pytest.raises(InvalidModelOutput):
            generator.generate(system="Respondé.", user="¿Qué?", timeout_seconds=0.25)
    finally:
        generator.close()

    assert seen["timeout"]["read"] == 0.25
