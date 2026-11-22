"""Contrato de despliegue de Qdrant para el corte 1.

No levanta servicios: valida los archivos y la interfaz de configuración.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from secguard_advisor.retrieval import instance

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "compose.qdrant.yml"
MAKEFILE = ROOT / "Makefile"
ENV_EXAMPLE = ROOT / ".env.example"
PYPROJECT = ROOT / "pyproject.toml"


def test_compose_pins_image_and_loopback_ports() -> None:
    content = COMPOSE.read_text(encoding="utf-8")

    assert "image: qdrant/qdrant:v1.20.0" in content
    assert '"127.0.0.1:6333:6333"' in content
    assert '"127.0.0.1:6334:6334"' in content
    assert "./storage/qdrant:/qdrant/storage" in content
    assert "restart: unless-stopped" in content
    assert "0.0.0.0:" not in content
    assert "network_mode: host" not in content


def test_env_example_declares_instance_and_qdrant_settings() -> None:
    content = ENV_EXAMPLE.read_text(encoding="utf-8")

    assert "SECGUARD_INSTANCE_ID=" in content
    assert "SECGUARD_QDRANT_URL=http://127.0.0.1:6333" in content
    assert "SECGUARD_QDRANT_TIMEOUT_SECONDS=5" in content
    assert "SECGUARD_STORAGE_DIR=./storage" in content


def test_makefile_exposes_qdrant_targets_in_help() -> None:
    makefile = MAKEFILE.read_text(encoding="utf-8")
    for target in ("qdrant-up", "qdrant-down", "qdrant-health"):
        assert f"{target}: ## " in makefile

    result = subprocess.run(
        ["make", "-s", "help"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    for target in ("qdrant-up", "qdrant-down", "qdrant-health"):
        assert target in result.stdout


def test_instance_namespace_contract() -> None:
    assert instance.instance_prefix("local-dev") == "secguard__local-dev__"
    assert "local-dev" in instance.instance_prefix("local-dev")
    for invalid in ("Local-Dev", "ab", "local/dev"):
        try:
            instance.instance_prefix(invalid)
        except instance.InstanceConfigurationError:
            continue
        raise AssertionError(f"{invalid!r} debería rechazarse")


def test_qdrant_is_the_only_declared_document_backend() -> None:
    content = PYPROJECT.read_text(encoding="utf-8")

    assert "qdrant-client==1.20.0" in content
    assert "langchain-chroma" not in content
    assert "chromadb" not in content
