"""Perfiles de configuración de IA: persistencia y precedencia (005 UI)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from secguard_advisor.ai_config.service import (
    AIConfigurationError,
    load_view,
    resolve_turn_settings,
    save_configuration,
)
from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import AIConfiguration, AIProviderProfile


def _settings(tmp_path: Path, **overrides) -> Settings:
    values = {
        "storage_dir": tmp_path / "storage",
        "generation_provider": "ollama",
        "generation_model": None,
        "generation_max_output_tokens": 64,
        "generation_timeout_seconds": 12.5,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def _factory(tmp_path: Path, settings: Settings):
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    return create_session_factory(engine)


def test_first_load_uses_environment_without_saved_configuration(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    factory = _factory(tmp_path, settings)

    with factory() as session:
        view = load_view(session, settings)

    assert view.saved is False
    assert view.active_provider == "ollama"
    assert view.active_profile.model == "qwen3.5:9b"
    assert view.active_profile.source == "environment"
    assert view.active_profile.max_output_tokens == 1200
    assert view.active_profile.timeout_seconds == 12.5
    assert view.global_budget_usd == Decimal("0")
    assert view.external_blocked is False


def test_save_and_reload_persists_active_profile(tmp_path: Path) -> None:
    settings = _settings(tmp_path, deepseek_api_key="secret")
    factory = _factory(tmp_path, settings)

    with factory() as session:
        saved = save_configuration(
            session,
            settings,
            provider="deepseek",
            model="deepseek-flash",
            max_output_tokens=128,
            timeout_seconds=15,
        )
        session.commit()
    assert saved.active_provider == "deepseek"
    assert saved.active_profile.source == "saved"
    assert saved.active_profile.credential_status == "configured"
    assert saved.external_blocked is True

    with factory() as session:
        reloaded = load_view(session, settings)
        assert reloaded.active_provider == "deepseek"
        assert reloaded.active_profile.model == "deepseek-flash"
        assert reloaded.active_profile.max_output_tokens == 128
        assert session.get(AIConfiguration, 1).active_provider == "deepseek"


def test_switching_provider_does_not_overwrite_other_profiles(tmp_path: Path) -> None:
    settings = _settings(tmp_path, deepseek_api_key="d", anthropic_api_key="a")
    factory = _factory(tmp_path, settings)

    with factory() as session:
        save_configuration(
            session,
            settings,
            provider="deepseek",
            model="deepseek-flash",
            max_output_tokens=111,
            timeout_seconds=11,
        )
        save_configuration(
            session,
            settings,
            provider="anthropic",
            model="claude-haiku-5-5",
            max_output_tokens=222,
            timeout_seconds=22,
        )
        session.commit()
        view = load_view(session, settings)
        profiles = list(session.scalars(select(AIProviderProfile)))

    assert view.active_provider == "anthropic"
    assert view.active_profile.max_output_tokens == 222
    assert {row.provider: row.max_output_tokens for row in profiles} == {
        "deepseek": 111,
        "anthropic": 222,
    }


def test_resolve_turn_settings_returns_active_profile(tmp_path: Path) -> None:
    settings = _settings(tmp_path, deepseek_api_key="secret")
    factory = _factory(tmp_path, settings)

    with factory() as session:
        save_configuration(
            session,
            settings,
            provider="deepseek",
            model="deepseek-flash",
            max_output_tokens=77,
            timeout_seconds=7.5,
        )
        session.commit()
        turn = resolve_turn_settings(session, settings)

    assert turn.generation_provider == "deepseek"
    assert turn.provider_model == "deepseek-flash"
    assert turn.provider_max_output_tokens == 77
    assert turn.provider_timeout_seconds == 7.5


def test_invalid_configuration_is_rejected(tmp_path: Path) -> None:
    settings = _settings(tmp_path, deepseek_api_key="secret")
    factory = _factory(tmp_path, settings)

    with factory() as session:
        with pytest.raises(AIConfigurationError, match="entre 1"):
            save_configuration(
                session,
                settings,
                provider="deepseek",
                model="deepseek-flash",
                max_output_tokens=0,
                timeout_seconds=10,
            )
        with pytest.raises(AIConfigurationError, match="tiempo máximo"):
            save_configuration(
                session,
                settings,
                provider="deepseek",
                model="deepseek-flash",
                max_output_tokens=10,
                timeout_seconds=0,
            )
        with pytest.raises(AIConfigurationError, match="otro proveedor"):
            save_configuration(
                session,
                settings,
                provider="deepseek",
                model="claude-haiku-5-5",
                max_output_tokens=10,
                timeout_seconds=10,
            )


def test_missing_credential_has_a_clear_message(tmp_path: Path) -> None:
    settings = _settings(tmp_path, deepseek_api_key=None, anthropic_api_key=None)
    factory = _factory(tmp_path, settings)

    with factory() as session, pytest.raises(AIConfigurationError, match="DEEPSEEK_API_KEY"):
        save_configuration(
            session,
            settings,
            provider="deepseek",
            model="deepseek-flash",
            max_output_tokens=10,
            timeout_seconds=10,
        )


def test_unconfirmed_model_is_saved_with_explicit_warning(tmp_path: Path) -> None:
    settings = _settings(tmp_path, deepseek_api_key="secret")
    factory = _factory(tmp_path, settings)

    with factory() as session:
        view = save_configuration(
            session,
            settings,
            provider="deepseek",
            model="deepseek-compatible-custom",
            max_output_tokens=10,
            timeout_seconds=10,
        )
    assert view.active_profile.model_status == "unconfirmed"
    assert view.active_profile.model == "deepseek-compatible-custom"


def test_ollama_ignores_commercial_budget_and_auto_reserves(tmp_path: Path) -> None:
    settings = _settings(tmp_path, external_budget_usd=Decimal("0"))
    factory = _factory(tmp_path, settings)

    with factory() as session:
        view = save_configuration(
            session,
            settings,
            provider="ollama",
            model="qwen3.5:9b",
            max_output_tokens=999_999,
            timeout_seconds=12.5,
        )
    assert view.active_profile.max_output_tokens == 1200
    assert view.active_profile.max_output_limit == 1200
    assert view.active_profile.max_output_tokens <= view.active_profile.context_window
    assert view.external_blocked is False
    assert view.global_budget_usd == Decimal("0")


def test_external_limits_are_validated_against_selected_provider(tmp_path: Path) -> None:
    settings = _settings(
        tmp_path,
        generation_provider="ollama",
        deepseek_api_key="d",
        anthropic_api_key="a",
    )
    factory = _factory(tmp_path, settings)

    with factory() as session:
        anthropic = save_configuration(
            session,
            settings,
            provider="anthropic",
            model="claude-haiku-5-5",
            max_output_tokens=100_000,
            timeout_seconds=20,
        )
        assert anthropic.active_profile.max_output_limit == 127_680
        with pytest.raises(AIConfigurationError, match="entre 1"):
            save_configuration(
                session,
                settings,
                provider="deepseek",
                model="deepseek-flash",
                max_output_tokens=200_000,
                timeout_seconds=20,
            )
        assert load_view(session, settings).active_provider == "anthropic"
