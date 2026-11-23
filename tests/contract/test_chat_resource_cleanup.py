"""Los recursos propios del turno se cierran en éxito, error y preparación fallida."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from tests.fixtures.conversation import build_env
from tests.fixtures.fakes import FakeEmbedder, FakeTokenCounter

from secguard_advisor.config import Settings
from secguard_advisor.conversation.llm import AnswerPayload, ModelUnavailable, ToolDecision
from secguard_advisor.conversation.providers import ProviderNotImplemented
from secguard_advisor.db.models import ProviderBudgetLedger
from secguard_advisor.web.app import create_app
from secguard_advisor.web.routes import chat as chat_routes

ORIGIN = {"Origin": "http://testserver"}
HTMX = {**ORIGIN, "HX-Request": "true"}


class _Tracking:
    def __init__(self, inner) -> None:
        self.inner = inner
        self.closed = False

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def close(self) -> None:
        self.closed = True


class _Generator:
    provider = "ollama"
    model = "qwen3.5:9b"
    identity = "digest-local"

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.closed = False
        self.last_usage = {"input_tokens": 10, "output_tokens": 2, "source": "observed"}

    def decide(self, **_kwargs):
        return ToolDecision(use_findings=False, arguments={})

    def generate(self, **_kwargs):
        if self.fail:
            raise ModelUnavailable("caído")
        return AnswerPayload(answer="respuesta", claims=[])

    def close(self) -> None:
        self.closed = True


def _settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, storage_dir=tmp_path / "storage")


def _app(env, generator, *, embedder, index, counter):
    settings = Settings(
        _env_file=None,
        storage_dir=env.settings.storage_dir,
        generation_provider="ollama",
    )
    app = create_app(
        settings,
        ollama_probe=lambda: True,
        embedder_factory=lambda: embedder,
        index_factory=lambda: index,
        token_counter=counter,
    )
    app.state.embedder_owned_by_turn = True
    app.state.index_owned_by_turn = True
    app.state.llm_owned_by_turn = True
    app.state.token_counter_owned_by_turn = True
    return app


def _run(monkeypatch, env, generator, *, create_error=None):
    embedder = _Tracking(FakeEmbedder())
    index = _Tracking(env.index)
    counter = _Tracking(FakeTokenCounter())
    app = _app(env, generator, embedder=embedder, index=index, counter=counter)

    def create(_self, **_kwargs):
        if create_error is not None:
            raise create_error
        return generator

    monkeypatch.setattr(chat_routes.ProviderRegistry, "create", create)
    monkeypatch.setattr(chat_routes, "build_prompt_counter", lambda _settings: counter)
    with TestClient(app) as client:
        response = client.post(
            f"/cases/{env.case_id}/chat/messages",
            data={"question": "¿Qué controles aplican?"},
            headers=HTMX,
        )
    return response, generator, embedder, index, counter, app


def test_owned_resources_close_after_success(tmp_path: Path, monkeypatch) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    generator = _Generator()
    response, _g, embedder, index, counter, app = _run(monkeypatch, env, generator)

    assert response.status_code == 200
    assert generator.closed is True
    assert embedder.closed is True
    assert index.closed is True
    assert counter.closed is True
    assert app.state.generation_slot.acquire() is True
    app.state.generation_slot.release()


def test_owned_resources_close_after_model_error(tmp_path: Path, monkeypatch) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    generator = _Generator(fail=True)
    response, _g, embedder, index, counter, app = _run(monkeypatch, env, generator)

    assert response.status_code == 503
    assert generator.closed is True
    assert embedder.closed is True
    assert index.closed is True
    assert counter.closed is True
    assert app.state.generation_slot.acquire() is True
    app.state.generation_slot.release()
    with env.factory() as session:
        assert session.scalar(select(ProviderBudgetLedger)) is None


def test_owned_resources_close_after_preparation_failure(tmp_path: Path, monkeypatch) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    generator = _Generator()
    response, _g, embedder, index, _counter, app = _run(
        monkeypatch,
        env,
        generator,
        create_error=ProviderNotImplemented("deepseek", "deepseek-flash"),
    )

    assert response.status_code == 501
    assert generator.closed is False
    assert embedder.closed is True
    assert index.closed is True
    assert app.state.generation_slot.acquire() is True
    app.state.generation_slot.release()
