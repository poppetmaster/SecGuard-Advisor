"""Contrato de la evidencia de ejecución con proveedor y costo (Entrega 1)."""

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from tests.fixtures.conversation import build_env
from tests.fixtures.fakes import FakeEmbedder, FakeTokenCounter, ScriptedGenerator

from secguard_advisor.conversation.llm import AnswerPayload
from secguard_advisor.db.models import Run
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
            run_id = session.scalar(select(Run.id).where(Run.case_id == env.case_id))
        page = client.get(f"/cases/{env.case_id}/runs/{run_id}")

    assert page.status_code == 200
    html = page.text
    assert "Proveedor" in html
    assert "ollama" in html
    assert "Identidad" in html
    assert "digest-observado" in html
    assert "No aplicable (API)" in html
    assert "no mide el costo operativo local" in html
    assert "super-secret" not in html
