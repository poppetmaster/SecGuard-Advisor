"""Pruebas de configuración y de la no exposición de secretos."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from secguard_advisor.config import Settings


def test_defaults_without_env_file() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_env == "development"
    assert settings.storage_dir == Path("storage")
    assert settings.database_url.endswith("/storage/secguard.sqlite3")
    assert settings.reviewer_name is None
    assert settings.generation_queue_timeout_seconds == 5.0
    assert settings.embedding_dim == 768


def test_environment_overrides(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SECGUARD_STORAGE_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("SECGUARD_REVIEWER_NAME", "  Revisor Local  ")
    monkeypatch.setenv("SECGUARD_GENERATION_QUEUE_TIMEOUT_SECONDS", "2.5")

    settings = Settings(_env_file=None)

    assert settings.storage_dir == tmp_path / "data"
    assert settings.reviewer_name == "Revisor Local"
    assert settings.generation_queue_timeout_seconds == 2.5


def test_blank_reviewer_is_none(monkeypatch) -> None:
    monkeypatch.setenv("SECGUARD_REVIEWER_NAME", "   ")

    settings = Settings(_env_file=None)

    assert settings.reviewer_name is None


def test_api_key_is_never_rendered(monkeypatch) -> None:
    monkeypatch.setenv("LANGSMITH_API_KEY", "super-secret")

    settings = Settings(_env_file=None)

    assert settings.langsmith_api_key is not None
    assert settings.langsmith_api_key.get_secret_value() == "super-secret"
    assert "super-secret" not in repr(settings)


def test_ensure_directories(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, storage_dir=tmp_path / "storage")

    settings.ensure_directories()

    assert settings.storage_dir.is_dir()
    assert settings.originals_dir.is_dir()


def test_qdrant_settings_default_to_local_loopback() -> None:
    settings = Settings(_env_file=None)

    assert settings.instance_id is None
    assert settings.qdrant_url == "http://127.0.0.1:6333"
    assert settings.qdrant_timeout_seconds == 5.0


def test_instance_id_and_qdrant_url_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("SECGUARD_INSTANCE_ID", "local-dev")
    monkeypatch.setenv("SECGUARD_QDRANT_URL", "http://127.0.0.1:6334")
    monkeypatch.setenv("SECGUARD_QDRANT_TIMEOUT_SECONDS", "2.5")

    settings = Settings(_env_file=None)

    assert settings.instance_id == "local-dev"
    assert settings.qdrant_url == "http://127.0.0.1:6334"
    assert settings.qdrant_timeout_seconds == 2.5


def test_blank_instance_id_is_none(monkeypatch) -> None:
    monkeypatch.setenv("SECGUARD_INSTANCE_ID", "   ")

    assert Settings(_env_file=None).instance_id is None


def test_invalid_instance_id_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("SECGUARD_INSTANCE_ID", "Local Dev")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_invalid_qdrant_url_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("SECGUARD_QDRANT_URL", "localhost:6333")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
