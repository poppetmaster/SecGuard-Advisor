"""Contrato: proveedor externo no implementado falla sin caer a Ollama."""

from pathlib import Path

from fastapi.testclient import TestClient
from tests.fixtures.conversation import build_env
from tests.fixtures.fakes import FakeEmbedder, FakeTokenCounter

from secguard_advisor.config import Settings
from secguard_advisor.web.app import create_app

ORIGIN = {"Origin": "http://testserver"}
HTMX = {**ORIGIN, "HX-Request": "true"}


def test_external_provider_returns_explicit_error_and_does_not_use_ollama(
    tmp_path: Path,
) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    external = Settings(
        _env_file=None,
        storage_dir=env.settings.storage_dir,
        generation_provider="deepseek",
        deepseek_api_key="deepseek-secret",
    )
    app = create_app(
        external,
        ollama_probe=lambda: True,
        embedder_factory=lambda: FakeEmbedder(),
        index_factory=lambda: env.index,
        token_counter=FakeTokenCounter(),
    )

    with TestClient(app) as client:
        response = client.post(
            f"/cases/{env.case_id}/chat/messages",
            data={"question": "¿Qué controles aplican?"},
            headers=HTMX,
        )

    assert response.status_code == 501
    assert "deepseek" in response.text
    assert "todavía no está implementado" in response.text
    assert "deepseek-secret" not in response.text
    assert "qwen3.5" not in response.text
