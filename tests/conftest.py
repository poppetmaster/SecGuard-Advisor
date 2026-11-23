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


@pytest.fixture(autouse=True)
def _test_retrieval_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    """Aísla las pruebas del umbral calibrado de producción.

    El umbral de `Settings` se calibra para Qdrant; las pruebas que no evalúan el
    filtro usan 0.0 para no depender de la similitud de los dobles.
    """
    monkeypatch.setenv("RETRIEVAL_MIN_SCORE", "0.0")


@pytest.fixture
def report_context(tmp_path: Path):
    """Contexto aislado con caso, snapshot confirmado y filas ficticias."""
    from tests.fixtures.report_fixtures import build_report_context

    return build_report_context(tmp_path)
