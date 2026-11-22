"""La configuración efectiva del generador se usa en contador, reserva y timeout."""

from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace

from secguard_advisor.config import Settings
from secguard_advisor.conversation.budget import plan_prompt, prompt_limit
from secguard_advisor.conversation.nodes import _model_timeout
from secguard_advisor.web.app import create_app


class _Counter:
    def count(self, system: str, user: str) -> int:
        return 10

    def describe(self) -> dict:
        return {"method": "fake"}


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        storage_dir=tmp_path / "storage",
        generation_model="effective-model",
        generation_max_output_tokens=64,
        generation_timeout_seconds=12.5,
    )


def test_prompt_limit_and_output_reserve_use_effective_values(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    assert prompt_limit(settings) == (
        settings.provider_context_window - 64 - settings.context_safety_margin_tokens
    )

    plan = plan_prompt(
        question="¿Qué controles aplican?",
        hits=(),
        history=(),
        settings=settings,
        counter=_Counter(),
    )

    assert plan.prompt_limit == prompt_limit(settings)
    assert plan.output_reserve == 64


def test_model_timeout_uses_effective_provider_timeout(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    context = SimpleNamespace(
        deps=SimpleNamespace(settings=settings),
        started_perf=time.perf_counter(),
    )

    assert _model_timeout(context) == 12.5


def test_app_counter_uses_effective_ollama_model(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    app = create_app(settings, ollama_probe=lambda: True)

    assert app.state.token_counter.describe()["model"] == "effective-model"
