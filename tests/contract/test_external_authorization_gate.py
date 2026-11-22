"""Contrato: la autorización y el presupuesto se comprueban antes de llamar."""

from pathlib import Path

from fastapi.testclient import TestClient
from tests.fixtures.conversation import build_env
from tests.fixtures.fakes import FakeEmbedder

from secguard_advisor.cases.external import authorize_case
from secguard_advisor.config import Settings
from secguard_advisor.web.app import create_app

ORIGIN = {"Origin": "http://testserver"}
HTMX = {**ORIGIN, "HX-Request": "true"}


class _ExplodingCounter:
    def count(self, system: str, user: str) -> int:
        raise AssertionError("no debe contarse un prompt externo sin autorización o presupuesto")

    def describe(self) -> dict:
        return {"method": "fake"}


class _ExplodingGenerator:
    provider = "deepseek"
    model = "deepseek-flash"
    identity = None
    last_usage = None

    def decide(self, **_kwargs):
        raise AssertionError("no debe llamarse sin autorización o presupuesto")

    def generate(self, **_kwargs):
        raise AssertionError("no debe llamarse sin autorización o presupuesto")

    def close(self) -> None:
        return None


def _external(env, *, budget: str = "0") -> Settings:
    return Settings(
        _env_file=None,
        storage_dir=env.settings.storage_dir,
        generation_provider="deepseek",
        deepseek_api_key="deepseek-secret",
        external_budget_usd=budget,
        external_run_budget_usd=budget,
    )


def test_external_provider_requires_authorization_before_any_call(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    app = create_app(
        _external(env, budget="1"),
        ollama_probe=lambda: True,
        embedder_factory=lambda: FakeEmbedder(),
        index_factory=lambda: env.index,
        llm_factory=lambda: _ExplodingGenerator(),
        token_counter=_ExplodingCounter(),
    )

    with TestClient(app) as client:
        response = client.post(
            f"/cases/{env.case_id}/chat/messages",
            data={"question": "¿Qué controles aplican?"},
            headers=HTMX,
        )

    assert response.status_code == 403
    assert "autorización" in response.text
    assert "deepseek-secret" not in response.text
    assert "qwen3.5" not in response.text


def test_authorized_external_provider_with_zero_budget_is_blocked(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    with env.factory() as session:
        authorize_case(
            session,
            case_id=env.case_id,
            scope="fictional_case",
            authorized_by="Revisora",
        )
        session.commit()
    app = create_app(
        _external(env, budget="0"),
        ollama_probe=lambda: True,
        embedder_factory=lambda: FakeEmbedder(),
        index_factory=lambda: env.index,
        llm_factory=lambda: _ExplodingGenerator(),
        token_counter=_ExplodingCounter(),
    )

    with TestClient(app) as client:
        response = client.post(
            f"/cases/{env.case_id}/chat/messages",
            data={"question": "¿Qué controles aplican?"},
            headers=HTMX,
        )

    assert response.status_code == 402
    assert "presupuesto" in response.text
    assert "deepseek-secret" not in response.text
