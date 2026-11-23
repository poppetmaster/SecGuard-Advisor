"""Adaptador DeepSeek Flash (OpenAI-compatible, JSON Output)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import httpx

from secguard_advisor.config import Settings
from secguard_advisor.conversation.llm import AnswerPayload, ToolDecision
from secguard_advisor.conversation.providers.http_common import (
    parse_structured,
    post_json,
    schema_instruction,
    usage_dict,
)


@dataclass
class DeepSeekGenerator:
    settings: Settings
    client: httpx.Client | None = None
    model: str = field(init=False)
    provider: str = field(init=False, default="deepseek")
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

    def generate_structured(self, *, system: str, user: str, schema, timeout_seconds=None):
        return self._structured(system, user, schema, timeout_seconds)

    def _structured(self, system: str, user: str, schema, timeout_seconds):
        started = time.perf_counter()
        self.last_usage = None
        api_key = self.settings.deepseek_api_key
        if api_key is None:
            from secguard_advisor.conversation.providers.base import ProviderAuthError

            raise ProviderAuthError("Falta la credencial de DeepSeek.")
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": schema_instruction(system, schema)},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": self.settings.provider_max_output_tokens,
            "stream": False,
            "thinking": {"type": "disabled"},
        }
        data = post_json(
            self.client,
            f"{self.settings.deepseek_base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key.get_secret_value()}",
                "content-type": "application/json",
            },
            payload=payload,
            timeout_seconds=timeout_seconds,
        )
        self.identity = data.get("model") or self.model
        usage = data.get("usage") or {}
        details = usage.get("completion_tokens_details") or {}
        self.last_usage = usage_dict(
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            cached_tokens=usage.get("prompt_cache_hit_tokens") or 0,
            cache_write_tokens=0,
            started=started,
            reasoning_tokens=details.get("reasoning_tokens"),
        )
        finish_reason = None
        try:
            choice = data["choices"][0]
            finish_reason = choice.get("finish_reason")
            content = choice["message"].get("content") or ""
        except (KeyError, IndexError, TypeError) as exc:
            from secguard_advisor.conversation.llm import InvalidModelOutput

            raise InvalidModelOutput(
                "DeepSeek devolvió una respuesta sin contenido.",
                reason="truncated_content"
                if finish_reason in {"length", "max_tokens"}
                else "empty_content",
            ) from exc
        return parse_structured(content, schema, finish_reason=finish_reason)

    def close(self) -> None:
        if getattr(self, "_owns_client", False) and self.client is not None:
            self.client.close()
