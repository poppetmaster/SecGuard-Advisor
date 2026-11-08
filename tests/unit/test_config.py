"""Pruebas de configuración y de la no exposición de secretos."""

from pathlib import Path

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
    assert settings.chroma_dir.is_dir()
    assert settings.originals_dir.is_dir()
