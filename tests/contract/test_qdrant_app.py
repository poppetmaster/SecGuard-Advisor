"""Contrato de la fábrica con Qdrant: construcción y errores de configuración."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from secguard_advisor.config import Settings
from secguard_advisor.retrieval.errors import IndexConfigurationError
from secguard_advisor.retrieval.index import QdrantIndex
from secguard_advisor.web.app import create_app


def _settings(tmp_path: Path, **overrides) -> Settings:
    return Settings(_env_file=None, storage_dir=tmp_path / "storage", **overrides)


def test_factory_builds_qdrant_without_connecting(tmp_path: Path) -> None:
    settings = _settings(tmp_path, instance_id="test-local")
    app = create_app(settings, ollama_probe=lambda: True)

    index = app.state.index_factory()

    assert isinstance(index, QdrantIndex)
    assert index.instance_id == "test-local"
    index.close()


def test_factory_fails_without_instance_id(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    app = create_app(settings, ollama_probe=lambda: True)

    with pytest.raises(IndexConfigurationError) as error:
        app.state.index_factory()

    assert "SECGUARD_INSTANCE_ID" in str(error.value)


def test_invalid_instance_id_fails_at_configuration(tmp_path: Path) -> None:
    with pytest.raises(ValidationError) as error:
        _settings(tmp_path, instance_id="Bad Id")

    assert "SECGUARD_INSTANCE_ID" in str(error.value)
