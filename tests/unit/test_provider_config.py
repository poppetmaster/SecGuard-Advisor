"""Pruebas de configuración del proveedor de generación (Entrega 1)."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from secguard_advisor.config import Settings

_PROVIDER_ENV = (
    "SECGUARD_GENERATION_PROVIDER",
    "SECGUARD_GENERATION_MODEL",
    "SECGUARD_GENERATION_MAX_OUTPUT_TOKENS",
    "SECGUARD_GENERATION_TIMEOUT_SECONDS",
    "SECGUARD_GENERATION_REASONING",
    "DEEPSEEK_API_KEY",
    "ANTHROPIC_API_KEY",
)


@pytest.fixture(autouse=True)
def _clean_provider_env(monkeypatch) -> None:
    for name in _PROVIDER_ENV:
        monkeypatch.delenv(name, raising=False)


def test_defaults_to_ollama_and_reuses_existing_settings() -> None:
    settings = Settings(_env_file=None)

    assert settings.generation_provider == "ollama"
    assert settings.provider_model == settings.ollama_model
    assert settings.provider_max_output_tokens == settings.generator_num_predict
    assert settings.provider_timeout_seconds == settings.llm_timeout_seconds
    assert settings.deepseek_api_key is None
    assert settings.anthropic_api_key is None


def test_new_generation_names_override_old_ollama_names(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_MODEL", "old-model")
    monkeypatch.setenv("SECGUARD_GENERATION_MODEL", "new-model")
    monkeypatch.setenv("SECGUARD_GENERATION_MAX_OUTPUT_TOKENS", "64")
    monkeypatch.setenv("SECGUARD_GENERATION_TIMEOUT_SECONDS", "12.5")

    settings = Settings(_env_file=None)

    assert settings.provider_model == "new-model"
    assert settings.provider_max_output_tokens == 64
    assert settings.provider_timeout_seconds == 12.5


def test_ollama_falls_back_to_old_names_when_new_ones_are_absent(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_MODEL", "legacy-model")
    monkeypatch.delenv("SECGUARD_GENERATION_MODEL", raising=False)

    settings = Settings(_env_file=None)

    assert settings.provider_model == "legacy-model"


def test_deepseek_requires_credential(monkeypatch) -> None:
    monkeypatch.setenv("SECGUARD_GENERATION_PROVIDER", "deepseek")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(ValidationError, match="DEEPSEEK_API_KEY"):
        Settings(_env_file=None)


def test_anthropic_requires_credential(monkeypatch) -> None:
    monkeypatch.setenv("SECGUARD_GENERATION_PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(ValidationError, match="ANTHROPIC_API_KEY"):
        Settings(_env_file=None)


def test_external_defaults_use_verified_model_names(monkeypatch) -> None:
    monkeypatch.setenv("SECGUARD_GENERATION_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-secret")

    deepseek = Settings(_env_file=None)
    assert deepseek.provider_model == "deepseek-flash"
    assert "deepseek-secret" not in repr(deepseek)

    monkeypatch.setenv("SECGUARD_GENERATION_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-secret")
    anthropic = Settings(_env_file=None)
    assert anthropic.provider_model == "claude-haiku-5-5"
    assert "anthropic-secret" not in repr(anthropic)


def test_unknown_provider_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("SECGUARD_GENERATION_PROVIDER", "openai")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize("value", ["0", "-1"])
def test_invalid_generation_limits_are_rejected(monkeypatch, value: str) -> None:
    monkeypatch.setenv("SECGUARD_GENERATION_MAX_OUTPUT_TOKENS", value)

    with pytest.raises(ValidationError, match="SECGUARD_GENERATION_MAX_OUTPUT_TOKENS"):
        Settings(_env_file=None)


def test_environment_overrides_dotenv(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SECGUARD_GENERATION_PROVIDER=anthropic\n"
        "SECGUARD_GENERATION_MODEL=from-file\n"
        "ANTHROPIC_API_KEY=file-secret\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SECGUARD_GENERATION_PROVIDER", "ollama")

    settings = Settings()

    assert settings.generation_provider == "ollama"
    assert settings.generation_model == "from-file"
    assert settings.anthropic_api_key is not None
