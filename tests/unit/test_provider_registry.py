"""Pruebas del registro explícito de proveedores (Entrega 1)."""

import pytest

from secguard_advisor.config import Settings
from secguard_advisor.conversation.providers.base import (
    GeneratorProtocol,
    ProviderNotImplemented,
)
from secguard_advisor.conversation.providers.registry import ProviderRegistry


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_registry_selects_ollama_with_effective_settings() -> None:
    settings = _settings(
        generation_provider="ollama",
        generation_model="modelo-nuevo",
        generation_max_output_tokens=64,
        generation_timeout_seconds=12.5,
    )

    generator = ProviderRegistry(settings).create(resolve_digest=False)

    assert isinstance(generator, GeneratorProtocol)
    assert generator.provider == "ollama"
    assert generator.model == "modelo-nuevo"
    assert generator.config.num_predict == 64
    assert generator.config.timeout_seconds == 12.5


def test_registry_reuses_legacy_ollama_model_when_new_name_is_absent() -> None:
    settings = _settings(ollama_model="legacy-model", generation_model=None)

    generator = ProviderRegistry(settings).create(resolve_digest=False)

    assert generator.model == "legacy-model"


@pytest.mark.parametrize(
    ("provider", "credential_name", "expected_model"),
    [
        ("deepseek", "deepseek_api_key", "deepseek-flash"),
        ("anthropic", "anthropic_api_key", "claude-haiku-5-5"),
    ],
)
def test_unimplemented_external_provider_fails_without_fallback(
    provider: str, credential_name: str, expected_model: str
) -> None:
    settings = _settings(
        generation_provider=provider,
        **{credential_name: "secret"},
    )

    with pytest.raises(ProviderNotImplemented) as error:
        ProviderRegistry(settings).create(resolve_digest=False)

    assert error.value.code == "provider_not_implemented"
    assert error.value.provider == provider
    assert error.value.model == expected_model
    assert "Ollama" in str(error.value)
