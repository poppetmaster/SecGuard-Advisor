"""Infraestructura de pruebas externas (T039), sin llamadas por defecto."""

from __future__ import annotations

import os

import pytest

from secguard_advisor.config import Settings

pytestmark = pytest.mark.external


def _settings() -> Settings:
    return Settings()


def test_external_execution_is_explicitly_authorized() -> None:
    if os.environ.get("SECGUARD_EXTERNAL_TESTS_AUTHORIZED") != "1":
        pytest.skip("Pruebas externas omitidas: falta SECGUARD_EXTERNAL_TESTS_AUTHORIZED=1.")
    settings = _settings()
    if settings.external_budget_usd <= 0 or settings.external_run_budget_usd <= 0:
        pytest.skip("Pruebas externas omitidas: presupuesto externo no habilitado.")
    if settings.deepseek_api_key is None or settings.anthropic_api_key is None:
        pytest.skip("Pruebas externas omitidas: faltan credenciales de proveedores.")
    # La autorización y el presupuesto están presentes; esta prueba no envía
    # solicitudes. La comparación externa real se ejecuta con un comando
    # explícito y conserva su propia evidencia.
    assert settings.external_budget_usd > 0
    assert settings.external_run_budget_usd > 0
