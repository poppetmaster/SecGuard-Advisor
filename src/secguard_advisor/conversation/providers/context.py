"""Contadores de prompt por proveedor.

Ollama usa el tokenizador GGUF del modelo local. Los proveedores externos usan
su propio mecanismo: Anthropic ofrece un endpoint gratuito de conteo; DeepSeek
usa una estimación conservadora identificada como tal. Una estimación no es un
conteo exacto ni una garantía contra truncamiento.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import httpx

from secguard_advisor.config import Settings
from secguard_advisor.conversation.tokenizer import LazyPromptCounter


@dataclass(frozen=True, slots=True)
class EstimatedPromptCounter:
    """Estimación conservadora por caracteres; se declara como estimación."""

    chars_per_token: float = 2.0
    overhead_tokens: int = 64

    def count(self, system: str, user: str) -> int:
        characters = len(system) + len(user)
        return max(1, math.ceil(characters / self.chars_per_token) + self.overhead_tokens)

    def describe(self) -> dict:
        return {
            "method": "estimated",
            "chars_per_token": self.chars_per_token,
            "overhead_tokens": self.overhead_tokens,
        }


class AnthropicPromptCounter:
    """Conteo con `POST /v1/messages/count_tokens`; si falla, estima."""

    def __init__(self, settings: Settings, *, client: httpx.Client | None = None) -> None:
        self._settings = settings
        self._client = client or httpx.Client(timeout=settings.provider_timeout_seconds)
        self._owns_client = client is None
        self._method = "count_tokens"
        self._fallback = EstimatedPromptCounter(
            settings.external_estimate_chars_per_token,
            settings.external_estimate_overhead_tokens,
        )

    def count(self, system: str, user: str) -> int:
        api_key = self._settings.anthropic_api_key
        if api_key is None:
            self._method = "estimated"
            return self._fallback.count(system, user)
        try:
            response = self._client.post(
                f"{self._settings.anthropic_base_url.rstrip('/')}/v1/messages/count_tokens",
                headers={
                    "x-api-key": api_key.get_secret_value(),
                    "anthropic-version": self._settings.anthropic_version,
                    "content-type": "application/json",
                },
                json={
                    "model": self._settings.provider_model,
                    "system": system,
                    "messages": [{"role": "user", "content": user}],
                },
            )
            if response.status_code == 200:
                self._method = "count_tokens"
                return int(response.json()["input_tokens"])
        except Exception:
            pass
        self._method = "estimated"
        return self._fallback.count(system, user)

    def describe(self) -> dict:
        detail = {"method": self._method, "model": self._settings.provider_model}
        if self._method == "estimated":
            detail.update(self._fallback.describe())
        return detail

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


def build_prompt_counter(settings: Settings) -> object:
    """Devuelve el contador del proveedor activo, sin usar GGUF para externos."""
    if settings.generation_provider == "ollama":
        return LazyPromptCounter(settings.provider_model)
    if settings.generation_provider == "anthropic":
        return AnthropicPromptCounter(settings)
    return EstimatedPromptCounter(
        settings.external_estimate_chars_per_token,
        settings.external_estimate_overhead_tokens,
    )
