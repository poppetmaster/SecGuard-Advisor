"""Contrato de la evidencia de ejecución con proveedor y costo (Entrega 1)."""

from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from tests.fixtures.conversation import build_env
from tests.fixtures.fakes import FakeEmbedder, FakeTokenCounter, ScriptedGenerator

from secguard_advisor.conversation.llm import AnswerPayload
from secguard_advisor.db.models import ProviderUsage, Run
from secguard_advisor.web.app import create_app

ORIGIN = {"Origin": "http://testserver"}
HTMX = {**ORIGIN, "HX-Request": "true"}


def _app(env, generator):
    return create_app(
        env.settings,
        ollama_probe=lambda: True,
        embedder_factory=lambda: FakeEmbedder(),
        index_factory=lambda: env.index,
        llm_factory=lambda: generator,
        token_counter=FakeTokenCounter(),
    )


def test_run_evidence_shows_provider_identity_and_non_applicable_cost(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    generator = ScriptedGenerator([AnswerPayload(answer="respuesta", claims=[])])
    generator.provider = "ollama"
    generator.identity = "digest-observado"

    with TestClient(_app(env, generator)) as client:
        client.post(
            f"/cases/{env.case_id}/chat/messages",
            data={"question": "¿Qué controles aplican?"},
            headers=HTMX,
        )
        with env.factory() as session:
            run = session.scalar(select(Run).where(Run.case_id == env.case_id))
            run.error_message = "fallo sk-abcdefgh12345678 en /Users/privado/archivo"
            session.commit()
            run_id = run.id
        page = client.get(f"/cases/{env.case_id}/runs/{run_id}")

    assert page.status_code == 200
    html = page.text
    assert "Proveedor" in html
    assert "ollama" in html
    assert "Identidad" in html
    assert "digest-observado" in html
    assert "No aplicable (API)" in html
    assert "Salida máxima" in html
    assert "Timeout de llamada" in html
    assert "Uso y costo" in html
    assert "no mide el costo operativo local" in html
    assert "super-secret" not in html
    assert "sk-abcdefgh12345678" not in html
    assert "[ruta]" in html


def test_run_evidence_renders_observed_usage_and_calculated_cost(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    generator = ScriptedGenerator([AnswerPayload(answer="respuesta", claims=[])])
    generator.provider = "ollama"
    generator.identity = "digest-ollama"

    with TestClient(_app(env, generator)) as client:
        client.post(
            f"/cases/{env.case_id}/chat/messages",
            data={"question": "¿Qué controles aplican?"},
            headers=HTMX,
        )
        with env.factory() as session:
            run = session.scalar(select(Run).where(Run.case_id == env.case_id))
            run.generator_provider = "deepseek"
            session.add(
                ProviderUsage(
                    run_id=run.id,
                    attempt_no=run.attempt_no,
                    operation="generate",
                    provider="deepseek",
                    model="deepseek-flash",
                    input_tokens=100,
                    output_tokens=20,
                    cached_tokens=0,
                    cache_write_tokens=0,
                    usage_source="observed",
                    duration_ms=12,
                    cost_usd=Decimal("0.000027"),
                    cost_status="calculated",
                    tariff_version="2026-11-22",
                )
            )
            session.commit()
            run_id = run.id
        page = client.get(f"/cases/{env.case_id}/runs/{run_id}")

    assert page.status_code == 200
    html = page.text
    assert "Uso y costo" in html
    assert "generate" in html
    assert "Calculado" in html
    assert "0.000027" in html
