"""Contrato del adaptador DeepSeek con transporte simulado."""

from __future__ import annotations

import json

import httpx
import pytest

from secguard_advisor.config import Settings
from secguard_advisor.conversation.llm import (
    AnswerPayload,
    InvalidModelOutput,
    ModelTimeout,
    ToolDecision,
)
from secguard_advisor.conversation.providers.base import ProviderAuthError, ProviderRateLimited
from secguard_advisor.conversation.providers.deepseek import DeepSeekGenerator


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        generation_provider="deepseek",
        generation_model="deepseek-flash",
        generation_max_output_tokens=64,
        deepseek_api_key="sk-deepseek-secret",
        deepseek_base_url="https://deepseek.test",
    )


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_decide_uses_json_output_and_records_usage() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "deepseek-flash",
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "use_findings": True,
                                    "arguments": {
                                        "origin": "synthetic",
                                        "severity": "High",
                                        "group_by": "asset",
                                    },
                                }
                            )
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 20,
                    "prompt_cache_hit_tokens": 10,
                },
            },
        )

    generator = DeepSeekGenerator(_settings(), client=_client(handler))
    try:
        decision = generator.decide(system="Clasificá.", user="¿Cuántos High por activo?")
    finally:
        generator.close()

    assert isinstance(decision, ToolDecision)
    assert decision.use_findings is True
    assert decision.arguments.severity == "High"
    assert seen["path"] == "/chat/completions"
    assert seen["auth"] == "Bearer sk-deepseek-secret"
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert seen["body"]["max_tokens"] == 64
    assert seen["body"]["thinking"] == {"type": "disabled"}
    assert "JSON" in seen["body"]["messages"][0]["content"]
    assert generator.identity == "deepseek-flash"
    assert generator.last_usage["input_tokens"] == 100
    assert generator.last_usage["cached_tokens"] == 10
    assert "sk-deepseek-secret" not in repr(generator.last_usage)


def test_generate_returns_a_validated_answer() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "deepseek-flash",
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "answer": "La restauración se prueba trimestralmente.",
                                    "claims": [],
                                    "missing_info": [],
                                    "recommendations": [],
                                }
                            )
                        }
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )

    generator = DeepSeekGenerator(_settings(), client=_client(handler))
    try:
        payload = generator.generate(system="Respondé.", user="¿Cada cuánto?")
    finally:
        generator.close()

    assert isinstance(payload, AnswerPayload)
    assert payload.answer.startswith("La restauración")


def test_timeout_does_not_reuse_previous_usage() -> None:
    calls = {"count": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": json.dumps({"use_findings": False})}}],
                    "usage": {"prompt_tokens": 120, "completion_tokens": 30},
                },
            )
        raise httpx.ReadTimeout("timeout")

    generator = DeepSeekGenerator(_settings(), client=_client(handler))
    try:
        generator.decide(system="Clasificá.", user="¿Qué?")
        assert generator.last_usage["input_tokens"] == 120
        with pytest.raises(ModelTimeout):
            generator.generate(system="Respondé.", user="¿Qué?")
        assert generator.last_usage is None
    finally:
        generator.close()


def test_invalid_json_keeps_the_reported_usage() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "no es json"}, "finish_reason": "length"}],
                "usage": {"prompt_tokens": 120, "completion_tokens": 30},
            },
        )

    generator = DeepSeekGenerator(_settings(), client=_client(handler))
    try:
        with pytest.raises(InvalidModelOutput) as captured:
            generator.generate(system="Respondé.", user="¿Qué?")
        assert captured.value.reason == "truncated_content"
        assert generator.last_usage is not None
        assert generator.last_usage["input_tokens"] == 120
        assert generator.last_usage["output_tokens"] == 30
    finally:
        generator.close()


def test_blank_content_is_invalid_output() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "   "}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 0},
            },
        )

    generator = DeepSeekGenerator(_settings(), client=_client(handler))
    try:
        with pytest.raises(InvalidModelOutput):
            generator.generate(system="Respondé.", user="¿Qué?")
    finally:
        generator.close()


@pytest.mark.parametrize(
    ("status", "error"),
    [(401, ProviderAuthError), (429, ProviderRateLimited)],
)
def test_error_statuses_are_normalized(status: int, error: type[Exception]) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": "sk-deepseek-secret"})

    generator = DeepSeekGenerator(_settings(), client=_client(handler))
    try:
        with pytest.raises(error) as captured:
            generator.generate(system="Respondé.", user="¿Qué?")
    finally:
        generator.close()

    assert "sk-deepseek-secret" not in str(captured.value)


def test_read_timeout_is_model_timeout() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout")

    generator = DeepSeekGenerator(_settings(), client=_client(handler))
    try:
        with pytest.raises(ModelTimeout):
            generator.generate(system="Respondé.", user="¿Qué?")
    finally:
        generator.close()


def test_per_call_timeout_reaches_the_transport() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["timeout"] = request.extensions.get("timeout")
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "{}"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), timeout=12.5)
    generator = DeepSeekGenerator(_settings(), client=client)
    try:
        with pytest.raises(InvalidModelOutput):
            generator.generate(system="Respondé.", user="¿Qué?", timeout_seconds=0.25)
    finally:
        generator.close()

    assert seen["timeout"]["read"] == 0.25
