"""Adaptador Anthropic Claude Haiku (Structured Outputs)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import httpx

from secguard_advisor.config import Settings
from secguard_advisor.conversation.llm import AnswerPayload, ToolDecision
from secguard_advisor.conversation.providers.http_common import (
    parse_structured,
    post_json,
    usage_dict,
)


def _normalize_schema(node):
    if isinstance(node, dict):
        if node.get("type") == "object":
            node["additionalProperties"] = False
        for value in node.values():
            _normalize_schema(value)
    elif isinstance(node, list):
        for item in node:
            _normalize_schema(item)
    return node


@dataclass
class AnthropicGenerator:
    settings: Settings
    client: httpx.Client | None = None
    model: str = field(init=False)
    provider: str = field(init=False, default="anthropic")
    identity: str | None = None
    last_usage: dict | None = None

    def __post_init__(self) -> None:
        self.model = self.settings.provider_model
        if self.client is None:
            self.client = httpx.Client(timeout=self.settings.provider_timeout_seconds)
            self._owns_client = True
        else:
            self._owns_client = False

    def decide(self, *, system: str, user: str, timeout_seconds=None) -> ToolDecision:
        return self._structured(system, user, ToolDecision, timeout_seconds)

    def generate(self, *, system: str, user: str, timeout_seconds=None) -> AnswerPayload:
        return self._structured(system, user, AnswerPayload, timeout_seconds)

    def _structured(self, system: str, user: str, schema, timeout_seconds):
        started = time.perf_counter()
        api_key = self.settings.anthropic_api_key
        if api_key is None:
            from secguard_advisor.conversation.providers.base import ProviderAuthError

            raise ProviderAuthError("Falta la credencial de Anthropic.")
        payload = {
            "model": self.model,
            "max_tokens": self.settings.provider_max_output_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "output_config": {
                "format": {
                    "type": "json_schema",
                    "schema": _normalize_schema(schema.model_json_schema()),
                }
            },
        }
        data = post_json(
            self.client,
            f"{self.settings.anthropic_base_url.rstrip('/')}/v1/messages",
            headers={
                "x-api-key": api_key.get_secret_value(),
                "anthropic-version": self.settings.anthropic_version,
                "content-type": "application/json",
            },
            payload=payload,
        )
        self.identity = data.get("model") or self.model
        content = "".join(
            block.get("text", "")
            for block in data.get("content", [])
            if block.get("type") == "text"
        )
        parsed = parse_structured(content, schema)
        usage = data.get("usage") or {}
        self.last_usage = usage_dict(
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            cached_tokens=usage.get("cache_read_input_tokens") or 0,
            cache_write_tokens=usage.get("cache_creation_input_tokens") or 0,
            started=started,
        )
        return parsed

    def close(self) -> None:
        if getattr(self, "_owns_client", False) and self.client is not None:
            self.client.close()
