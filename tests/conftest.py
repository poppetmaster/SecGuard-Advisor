"""Fixtures compartidas de pytest."""

from pathlib import Path

import pytest


@pytest.fixture
def tmp_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Directorio de almacenamiento temporal aislado por prueba."""
    storage = tmp_path / "storage"
    storage.mkdir()
    monkeypatch.setenv("SECGUARD_STORAGE_DIR", str(storage))
    return storage


@pytest.fixture
def sqlite_url(tmp_path: Path) -> str:
    """URL de una base SQLite temporal aislada por prueba."""
    return f"sqlite:///{tmp_path / 'test.sqlite3'}"
