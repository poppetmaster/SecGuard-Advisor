"""Integración real del registro con Ollama (Entrega 1).

La regresión de consulta con cita, memoria y herramienta se ejecuta con
`tests/acceptance/test_journey_real.py`, que ahora construye el generador a
través de `ProviderRegistry`. Esta prueba comprueba la conexión real del
registro y una llamada estructurada.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from secguard_advisor.config import Settings
from secguard_advisor.conversation.llm import ToolDecision
from secguard_advisor.conversation.providers import ProviderRegistry

pytestmark = pytest.mark.integration


def test_registry_creates_a_real_ollama_generator(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, storage_dir=tmp_path / "storage")
    generator = ProviderRegistry(settings).create()

    try:
        assert generator.provider == "ollama"
        assert generator.model == settings.provider_model
        decision = generator.decide(
            system=(
                "Decide si hace falta consultar hallazgos del caso. "
                "Responde con el esquema ToolDecision."
            ),
            user="¿Cuál es la capital de Francia? No hay hallazgos involucrados.",
        )
        assert isinstance(decision, ToolDecision)
        assert decision.use_findings is False
        assert generator.last_usage is not None
        assert generator.last_usage.get("prompt_tokens", 0) > 0
    finally:
        generator.close()
