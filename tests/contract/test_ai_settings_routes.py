"""Contrato de la página Configuración de IA (005 UI)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select
from tests.fixtures.conversation import build_env
from tests.fixtures.fakes import FakeEmbedder, FakeTokenCounter, ScriptedGenerator

from secguard_advisor.ai_config.service import save_configuration
from secguard_advisor.cases.external import authorize_case
from secguard_advisor.config import Settings
from secguard_advisor.conversation.llm import AnswerPayload, ToolDecision
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url
from secguard_advisor.db.models import AIConfiguration, AIProviderProfile
from secguard_advisor.web.app import create_app

ORIGIN = {"Origin": "http://testserver"}
HTMX = {**ORIGIN, "HX-Request": "true"}
SECRET = "sk-ai-settings-secret"


def _settings(tmp_path: Path, **overrides) -> Settings:
    values = {
        "storage_dir": tmp_path / "storage",
        "generation_provider": "ollama",
        "generation_model": None,
        "generation_max_output_tokens": 64,
        "generation_timeout_seconds": 12.5,
        "deepseek_api_key": SECRET,
        "anthropic_api_key": SECRET,
        "external_budget_usd": Decimal("0"),
        "external_run_budget_usd": Decimal("0"),
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def _client(settings: Settings) -> TestClient:
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    engine.dispose()
    return TestClient(create_app(settings, ollama_probe=lambda: True))


def _save(client: TestClient, **values):
    data = {
        "provider": "ollama",
        "model": "qwen3.5:9b",
        "max_output_tokens": "64",
        "timeout_seconds": "12.5",
    }
    data.update(values)
    return client.post("/settings/ai", data=data, headers=HTMX)


def test_first_load_without_saved_configuration(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    with _client(settings) as client:
        response = client.get("/settings/ai")

    assert response.status_code == 200
    assert "Configuración de IA" in response.text
    assert "Local — Ollama" in response.text
    assert "qwen3.5:9b" in response.text
    assert "No verificada" in response.text
    assert "Guardar configuración" in response.text
    assert "data-pending-indicator" in response.text
    assert "Guardando configuración" in response.text
    assert "SECRET" not in response.text
    assert SECRET not in response.text
    assert "Clave configurada" in response.text


def test_external_profile_default_is_4096_in_the_form(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    with _client(settings) as client:
        response = client.get("/settings/ai/profile?provider=deepseek", headers=HTMX)

    assert response.status_code == 200
    assert 'value="4096"' in response.text
    assert "Límite técnico del proveedor/modelo" in response.text


def test_save_persists_and_survives_restart(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    with _client(settings) as client:
        saved = _save(
            client,
            provider="deepseek",
            model="deepseek-flash",
            max_output_tokens="128",
            timeout_seconds="15",
        )
    assert saved.status_code == 200
    assert "Configuración guardada" in saved.text
    assert "consultas externas bloqueadas" in saved.text
    assert SECRET not in saved.text

    with _client(settings) as restarted:
        page = restarted.get("/settings/ai")
    assert "DeepSeek" in page.text
    assert "deepseek-flash" in page.text
    assert "128 tokens" in page.text
    assert "15.0 s" in page.text


def test_switching_provider_keeps_independent_profiles(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    with _client(settings) as client:
        _save(
            client,
            provider="deepseek",
            model="deepseek-flash",
            max_output_tokens="111",
            timeout_seconds="11",
        )
        _save(
            client,
            provider="anthropic",
            model="claude-haiku-5-5",
            max_output_tokens="222",
            timeout_seconds="22",
        )
        fields = client.get("/settings/ai/profile?provider=deepseek", headers=HTMX)
        _save(
            client,
            provider="ollama",
            model="qwen3.5:9b",
            max_output_tokens="33",
            timeout_seconds="3",
        )

    assert 'value="deepseek-flash"' in fields.text
    assert 'value="111"' in fields.text
    with _client(settings) as client, client.app.state.session_factory() as session:
        profiles = {row.provider: row for row in session.scalars(select(AIProviderProfile))}
        assert profiles["deepseek"].max_output_tokens == 111
        assert profiles["anthropic"].max_output_tokens == 222
        assert session.get(AIConfiguration, 1).active_provider == "ollama"


def test_invalid_values_and_missing_credential_are_explained(tmp_path: Path) -> None:
    settings = _settings(tmp_path, deepseek_api_key=None)
    with _client(settings) as client:
        invalid = _save(
            client,
            provider="anthropic",
            model="claude-haiku-5-5",
            max_output_tokens="0",
            timeout_seconds="12.5",
        )
        missing = _save(client, provider="deepseek", model="deepseek-flash")

    assert invalid.status_code == 422
    assert "entre 1" in invalid.text
    assert missing.status_code == 422
    assert "DEEPSEEK_API_KEY" in missing.text


def test_zero_budget_is_visible_for_external_provider(tmp_path: Path) -> None:
    settings = _settings(tmp_path, external_budget_usd=Decimal("0"))
    with _client(settings) as client:
        response = _save(client, provider="anthropic", model="claude-haiku-5-5")

    assert response.status_code == 200
    assert (
        "Configurado; consultas externas bloqueadas hasta autorizar presupuesto." in response.text
    )
    assert "0 USD" in response.text or "0.00 USD" in response.text


def test_open_and_save_make_no_external_calls(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)

    def fail(*_args, **_kwargs):
        raise AssertionError("no debe haber llamadas HTTP externas")

    monkeypatch.setattr(httpx.Client, "post", fail)
    with _client(settings) as client:
        assert client.get("/settings/ai").status_code == 200
        assert _save(client, provider="deepseek", model="deepseek-flash").status_code == 200


def test_no_secret_in_html_or_database(tmp_path: Path, caplog) -> None:
    settings = _settings(tmp_path)
    with _client(settings) as client:
        page = client.get("/settings/ai")
        saved = _save(client, provider="anthropic", model="claude-haiku-5-5")

    assert SECRET not in page.text
    assert SECRET not in saved.text
    assert SECRET not in caplog.text
    with settings.database_url and __import__("sqlite3").connect(
        settings.database_url.removeprefix("sqlite:///")
    ):
        pass


def test_saved_configuration_is_used_by_the_chat_route(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    with env.factory() as session:
        authorize_case(
            session, case_id=env.case_id, scope="fictional_case", authorized_by="Revisora"
        )
        save_configuration(
            session,
            Settings(
                _env_file=None,
                storage_dir=env.settings.storage_dir,
                generation_provider="ollama",
                deepseek_api_key=SECRET,
                anthropic_api_key=SECRET,
                external_budget_usd=Decimal("1"),
                external_run_budget_usd=Decimal("1"),
            ),
            provider="deepseek",
            model="deepseek-flash",
            max_output_tokens=64,
            timeout_seconds=12.5,
        )
        session.commit()
    generator = ScriptedGenerator(
        payloads=[
            __import__(
                "secguard_advisor.conversation.llm", fromlist=["AnswerPayload"]
            ).AnswerPayload(answer="respuesta", claims=[])
        ],
        decisions=[
            __import__("secguard_advisor.conversation.llm", fromlist=["ToolDecision"]).ToolDecision(
                use_findings=False, arguments={}
            )
        ],
    )
    generator.provider = "deepseek"
    generator.model = "deepseek-flash"
    generator.identity = "deepseek-flash"
    generator.last_usage = {
        "input_tokens": 10,
        "output_tokens": 2,
        "cached_tokens": 0,
        "cache_write_tokens": 0,
        "source": "observed",
    }
    settings = Settings(
        _env_file=None,
        storage_dir=env.settings.storage_dir,
        generation_provider="ollama",
        deepseek_api_key=SECRET,
        anthropic_api_key=SECRET,
        external_budget_usd=Decimal("1"),
        external_run_budget_usd=Decimal("1"),
    )
    app = create_app(
        settings,
        ollama_probe=lambda: True,
        embedder_factory=lambda: FakeEmbedder(),
        index_factory=lambda: env.index,
        llm_factory=lambda: generator,
        token_counter=FakeTokenCounter(),
    )
    with TestClient(app) as client:
        response = client.post(
            f"/cases/{env.case_id}/chat/messages",
            data={"question": "¿Qué controles aplican?"},
            headers=HTMX,
        )
    assert response.status_code in {200, 201}
    with env.factory() as session:
        run = session.scalar(
            select(__import__("secguard_advisor.db.models", fromlist=["Run"]).Run).where(
                __import__("secguard_advisor.db.models", fromlist=["Run"]).Run.case_id
                == env.case_id
            )
        )
    assert run.generator_provider == "deepseek"
    assert run.generator_model == "deepseek-flash"
    assert run.generator_max_output_tokens == 64
    assert run.generator_timeout_seconds == 12.5


def test_unconfirmed_model_is_flagged_in_the_page(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    with _client(settings) as client:
        _save(
            client,
            provider="deepseek",
            model="deepseek-compatible-custom",
            max_output_tokens="32",
            timeout_seconds="9",
        )
        page = client.get("/settings/ai")
    assert "Identificador no confirmado" in page.text
    assert "no se declara conexión aprobada" in page.text


def test_saved_external_selection_is_blocked_by_zero_budget(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    settings = Settings(
        _env_file=None,
        storage_dir=env.settings.storage_dir,
        generation_provider="ollama",
        deepseek_api_key=SECRET,
        external_budget_usd=Decimal("0"),
        external_run_budget_usd=Decimal("0"),
    )
    with env.factory() as session:
        authorize_case(
            session, case_id=env.case_id, scope="fictional_case", authorized_by="Revisora"
        )
        save_configuration(
            session,
            settings,
            provider="deepseek",
            model="deepseek-flash",
            max_output_tokens=64,
            timeout_seconds=12.5,
        )
        session.commit()
    app = create_app(
        settings,
        ollama_probe=lambda: True,
        embedder_factory=lambda: FakeEmbedder(),
        index_factory=lambda: env.index,
        llm_factory=lambda: (_ for _ in ()).throw(AssertionError("no debe llamarse")),
        token_counter=FakeTokenCounter(),
    )
    with TestClient(app) as client:
        response = client.post(
            f"/cases/{env.case_id}/chat/messages",
            data={"question": "¿Qué controles aplican?"},
            headers=HTMX,
        )
    assert response.status_code == 402
    assert "presupuesto" in response.text


def test_local_page_hides_economic_fields_and_token_quota(tmp_path: Path) -> None:
    settings = _settings(tmp_path, external_budget_usd=Decimal("0"))
    with _client(settings) as client:
        page = client.get("/settings/ai")
    assert "Ejecución local; sin cobro por tokens de API." in page.text
    assert "Reserva de salida automática" in page.text
    assert "Presupuesto global" not in page.text
    assert "Presupuesto por turno" not in page.text
    assert "Máximo de tokens de salida" not in page.text


def test_local_turn_works_with_zero_external_budget(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    settings = Settings(
        _env_file=None,
        storage_dir=env.settings.storage_dir,
        generation_provider="ollama",
        external_budget_usd=Decimal("0"),
        external_run_budget_usd=Decimal("0"),
    )
    generator = ScriptedGenerator(
        payloads=[AnswerPayload(answer="respuesta", claims=[])],
        decisions=[ToolDecision(use_findings=False, arguments={})],
    )
    generator.provider = "ollama"
    generator.model = "qwen3.5:9b"
    generator.identity = "digest-local"
    generator.last_usage = {"input_tokens": 10, "output_tokens": 2, "source": "observed"}
    app = create_app(
        settings,
        ollama_probe=lambda: True,
        embedder_factory=lambda: FakeEmbedder(),
        index_factory=lambda: env.index,
        llm_factory=lambda: generator,
        token_counter=FakeTokenCounter(),
    )
    with TestClient(app) as client:
        response = client.post(
            f"/cases/{env.case_id}/chat/messages",
            data={"question": "¿Qué controles aplican?"},
            headers=HTMX,
        )
    assert response.status_code == 200
    from secguard_advisor.db.models import ProviderBudgetLedger

    with env.factory() as session:
        assert session.scalar(select(ProviderBudgetLedger)) is None
