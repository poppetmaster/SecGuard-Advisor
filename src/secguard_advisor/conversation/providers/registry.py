"""Registro de proveedores con selección explícita y sin fallback."""

from __future__ import annotations

from dataclasses import dataclass

from secguard_advisor.config import Settings
from secguard_advisor.conversation.llm import GenerationConfig, OllamaGenerator
from secguard_advisor.conversation.providers.base import (
    GeneratorProtocol,
    ProviderNotImplemented,
)


@dataclass(frozen=True, slots=True)
class ProviderRegistry:
    """Resuelve el generador una sola vez por turno desde la configuración."""

    settings: Settings

    def create(self, *, resolve_digest: bool = True) -> GeneratorProtocol:
        provider = self.settings.generation_provider
        model = self.settings.provider_model
        if provider == "ollama":
            generator = OllamaGenerator(
                GenerationConfig(
                    base_url=self.settings.ollama_base_url,
                    model=model,
                    num_ctx=self.settings.generator_num_ctx,
                    num_predict=self.settings.provider_max_output_tokens,
                    temperature=self.settings.generator_temperature,
                    seed=self.settings.generator_seed,
                    timeout_seconds=self.settings.provider_timeout_seconds,
                )
            )
            if resolve_digest:
                generator.digest = generator.resolve_digest()
            return generator
        raise ProviderNotImplemented(provider, model)
