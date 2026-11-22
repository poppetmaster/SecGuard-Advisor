"""Conteo de contexto por proveedor (Entrega 2)."""

from __future__ import annotations

import json

import httpx

from secguard_advisor.config import Settings
from secguard_advisor.conversation.providers.context import (
    AnthropicPromptCounter,
    EstimatedPromptCounter,
    build_prompt_counter,
)


def _anthropic_settings() -> Settings:
    return Settings(
        _env_file=None,
        generation_provider="anthropic",
        anthropic_api_key="sk-ant-secret",
        anthropic_base_url="https://anthropic.test",
        anthropic_version="2026-10-21",
    )


def test_estimate_is_identified_as_estimate() -> None:
    counter = EstimatedPromptCounter(chars_per_token=2.0, overhead_tokens=10)

    count = counter.count("sistema", "usuario")

    assert count > 0
    assert counter.describe()["method"] == "estimated"


def test_anthropic_uses_the_count_tokens_endpoint() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["key"] = request.headers["x-api-key"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"input_tokens": 123})

    counter = AnthropicPromptCounter(
        _anthropic_settings(), client=httpx.Client(transport=httpx.MockTransport(handler))
    )

    try:
        assert counter.count("sistema", "usuario") == 123
    finally:
        counter.close()

    assert seen["path"] == "/v1/messages/count_tokens"
    assert seen["key"] == "sk-ant-secret"
    assert seen["body"]["model"] == "claude-haiku-5-5"
    assert counter.describe()["method"] == "count_tokens"


def test_anthropic_falls_back_to_estimate_and_says_so() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "down"})

    counter = AnthropicPromptCounter(
        _anthropic_settings(), client=httpx.Client(transport=httpx.MockTransport(handler))
    )

    try:
        assert counter.count("sistema", "usuario") > 0
    finally:
        counter.close()

    assert counter.describe()["method"] == "estimated"


def test_build_prompt_counter_selects_by_provider(tmp_path) -> None:
    ollama = Settings(
        _env_file=None,
        storage_dir=tmp_path / "ollama",
        generation_model="ollama-new",
    )
    deepseek = Settings(
        _env_file=None,
        storage_dir=tmp_path / "deepseek",
        generation_provider="deepseek",
        deepseek_api_key="secret",
    )

    ollama_counter = build_prompt_counter(ollama)
    deepseek_counter = build_prompt_counter(deepseek)

    assert ollama_counter.describe()["model"] == "ollama-new"
    assert deepseek_counter.describe()["method"] == "estimated"
