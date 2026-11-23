"""Contrato de la página Uso y comparativos de IA."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient

from secguard_advisor.ai_usage.evaluation_import import import_evaluation
from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import AiRequest, Case, Conversation, Run
from secguard_advisor.web.app import create_app

SECRET = "sk-usage-secret"
EVIDENCE = Path("docs/evidencia/005-evaluacion-proveedores")


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        storage_dir=tmp_path / "storage",
        generation_provider="ollama",
        generation_model="qwen3.5:9b",
        generation_max_output_tokens=64,
        deepseek_api_key=SECRET,
        anthropic_api_key=SECRET,
        external_budget_usd=Decimal("5"),
        external_run_budget_usd=Decimal("5"),
    )


def _client(settings: Settings) -> TestClient:
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        case = Case(id="case-1", title="Caso ficticio", synthetic_notice="Sintético.")
        session.add(case)
        session.flush()
        session.add(Conversation(id="conv-1", case_id=case.id, thread_id="t"))
        session.flush()
        session.add(
            Run(
                id="run-1",
                case_id=case.id,
                conversation_id="conv-1",
                status="succeeded",
                generator_provider="deepseek",
                generator_model="deepseek-flash",
                generator_num_ctx=8192,
                generator_temperature=0.1,
                embedding_model="embeddinggemma",
                embedding_dim=768,
                prompt_version="chat-v8",
                duration_ms=1500,
                usage_input_tokens=100,
                usage_output_tokens=20,
                usage_source="observed",
                cost_status="calculated",
                cost_usd=Decimal("0.001"),
                cost_tariff_version="2026-11-22",
                started_at="2026-01-15T15:00:00+00:00",
            )
        )
        session.flush()
        session.add(
            AiRequest(
                id="req-1",
                run_id="run-1",
                operation="generate",
                attempt_no=1,
                provider="deepseek",
                model="deepseek-flash",
                started_at="2026-01-15T15:00:01+00:00",
                finished_at="2026-01-15T15:00:02+00:00",
                status="completed",
                duration_ms=500,
                input_tokens=100,
                output_tokens=20,
                cached_tokens=0,
                usage_source="observed",
                cost_status="calculated",
                cost_usd=Decimal("0.001"),
                currency="USD",
                tariff_version="2026-11-22",
            )
        )
        session.commit()
    engine.dispose()
    return TestClient(create_app(settings, ollama_probe=lambda: True))


def test_panel_is_reachable_from_administration(tmp_path: Path) -> None:
    with _client(_settings(tmp_path)) as client:
        response = client.get(
            "/settings/ai/usage",
            params={"from": "2026-01-01", "to": "2026-01-31"},
        )

    assert response.status_code == 200
    text = response.text
    assert "Uso y comparativos de IA" in text
    assert "Configuración de IA" in text
    navigation = text[text.index("Navegación principal") :]
    assert navigation.index("Configuración de IA") < navigation.index("Uso y comparativos de IA")
    assert "Costo de API calculado" in text
    assert "Solicitudes API externas" in text
    assert "Llamadas locales" in text
    assert "Latencia mediana del turno" in text
    assert "Costo conocido de API por día" in text
    assert "Solicitudes API y llamadas locales por día" in text
    assert "Tokens de entrada y salida por proveedor" in text
    assert "Ver tabla accesible" in text
    assert 'data-echarts="consumption-cost"' in text
    assert 'data-echarts="consumption-requests"' in text
    assert 'data-echarts="consumption-tokens"' in text
    assert "/static/js/echarts.min.js" in text
    assert "/static/js/usage-charts.js" in text
    assert "Exportar PNG" in text
    assert "deepseek-flash" in text
    assert "Ver ejecución" in text
    assert SECRET not in text


def test_filters_and_invalid_range(tmp_path: Path) -> None:
    with _client(_settings(tmp_path)) as client:
        response = client.get(
            "/settings/ai/usage",
            params={"from": "2026-01-01", "to": "2026-01-31", "provider": "deepseek"},
        )
        invalid = client.get(
            "/settings/ai/usage", params={"from": "2026-02-01", "to": "2026-01-01"}
        )

    assert response.status_code == 200
    assert "2026-01-01" in response.text
    assert "2026-01-31" in response.text
    assert invalid.status_code == 200
    assert "fecha inicial" in invalid.text.lower()


def test_empty_state_and_htmx_fragment(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    engine.dispose()
    with TestClient(create_app(settings, ollama_probe=lambda: True)) as client:
        full = client.get("/settings/ai/usage")
        fragment = client.get("/settings/ai/usage", headers={"HX-Request": "true"})

    assert "Sin consultas registradas" in full.text
    assert "No hay solicitudes registradas" in full.text
    assert "<html" not in fragment.text
    assert 'id="ai-usage-panel"' in fragment.text


def test_comparison_tab_after_idempotent_import(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        import_evaluation(session, EVIDENCE)
        session.commit()
    engine.dispose()
    with TestClient(create_app(settings, ollama_probe=lambda: True)) as client:
        response = client.get("/settings/ai/usage", params={"tab": "comparison"})

    text = response.text
    assert response.status_code == 200
    assert "Comparativo de pruebas" in text
    assert "Histórico agregado" in text
    assert "Escenarios comunes" in text
    assert "S01" in text
    assert "Revisión humana registrada" in text
    assert "AI-assisted" in text
    assert "Consumo completo por proveedor" in text
    assert "Costo conocido parcial" in text
    assert "0.006201" in text
    assert "0.006150" in text
    assert "Comparativo funcional" in text
    assert "Muestra: 9 escenarios" in text
    assert "6/9" in text


def test_page_does_not_invoke_a_generator(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    def explode():
        raise AssertionError("El panel no debe crear un generador")

    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    engine.dispose()
    with TestClient(create_app(settings, ollama_probe=lambda: True, llm_factory=explode)) as client:
        response = client.get("/settings/ai/usage")
        comparison = client.get("/settings/ai/usage", params={"tab": "comparison"})

    assert response.status_code == 200
    assert comparison.status_code == 200
