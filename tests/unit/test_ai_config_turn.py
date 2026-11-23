"""La configuración guardada se aplica a turnos nuevos y no a uno en curso."""

from __future__ import annotations

import time
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from tests.fixtures.conversation import build_env
from tests.fixtures.fakes import FakeEmbedder, FakeTokenCounter, ScriptedGenerator

from secguard_advisor.ai_config.service import (
    resolve_turn_settings,
    save_configuration,
)
from secguard_advisor.cases.external import authorize_case
from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.conversation.budget import prompt_limit
from secguard_advisor.conversation.llm import AnswerPayload, ModelUnavailable
from secguard_advisor.conversation.nodes import _model_timeout
from secguard_advisor.conversation.providers.context import build_prompt_counter
from secguard_advisor.conversation.retry import start_retry_turn
from secguard_advisor.conversation.turn import execute_turn, start_question_turn
from secguard_advisor.db.models import Run


def _external(env, *, budget: str = "1") -> Settings:
    return Settings(
        _env_file=None,
        storage_dir=env.settings.storage_dir,
        generation_provider="ollama",
        deepseek_api_key="secret",
        anthropic_api_key="secret",
        external_budget_usd=Decimal(budget),
        external_run_budget_usd=Decimal(budget),
    )


def _fake(provider: str = "deepseek", *, failing: bool = False) -> ScriptedGenerator:
    generator = ScriptedGenerator(
        payloads=[AnswerPayload(answer="respuesta", claims=[])],
        decisions=[],
        error=ModelUnavailable("caído") if failing else None,
    )
    generator.provider = provider
    generator.model = "deepseek-flash" if provider == "deepseek" else "qwen3.5:9b"
    generator.identity = generator.model
    generator.last_usage = {
        "input_tokens": 10,
        "output_tokens": 2,
        "cached_tokens": 0,
        "cache_write_tokens": 0,
        "source": "observed",
    }
    return generator


def _save(env, settings, provider: str, model: str, output: int, timeout: float):
    with env.factory() as session:
        save_configuration(
            session,
            settings,
            provider=provider,
            model=model,
            max_output_tokens=output,
            timeout_seconds=timeout,
        )
        session.commit()


def _authorize(env) -> None:
    with env.factory() as session:
        authorize_case(
            session, case_id=env.case_id, scope="fictional_case", authorized_by="Revisora"
        )
        session.commit()


def _ask(env, settings, generator):
    return start_question_turn(
        env.factory,
        settings,
        scope=CaseScope(case_id=env.case_id),
        question="¿Qué controles aplican?",
        generator=generator,
        embedder=FakeEmbedder(),
        index=env.index,
        token_counter=FakeTokenCounter(),
    )


def test_saved_profile_is_used_by_a_new_turn(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    _authorize(env)
    settings = _external(env)
    _save(env, settings, "deepseek", "deepseek-flash", 64, 12.5)
    with env.factory() as session:
        turn_settings = resolve_turn_settings(session, settings)

    context = _ask(env, turn_settings, _fake())
    with env.factory() as session:
        run = session.get(Run, context.run_id)
    assert run.generator_provider == "deepseek"
    assert run.generator_model == "deepseek-flash"
    assert run.generator_max_output_tokens == 64
    assert run.generator_timeout_seconds == 12.5
    assert run.external_authorization_id is not None


def test_inflight_turn_keeps_its_profile_when_selection_changes(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    settings = _external(env)
    _save(env, settings, "ollama", "qwen3.5:9b", 64, 12.5)
    with env.factory() as session:
        old = resolve_turn_settings(session, settings)
    context = _ask(env, old, _fake("ollama"))

    _save(env, settings, "deepseek", "deepseek-flash", 222, 22)
    execute_turn(context)

    with env.factory() as session:
        run = session.get(Run, context.run_id)
        assert run.generator_provider == "ollama"
        assert run.generator_max_output_tokens == 1200
        assert run.generator_timeout_seconds == 12.5
        new = resolve_turn_settings(session, settings)
    assert new.generation_provider == "deepseek"
    assert new.provider_max_output_tokens == 222


def test_retry_uses_current_profile_and_keeps_effective_values(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    _authorize(env)
    settings = _external(env)
    _save(env, settings, "deepseek", "deepseek-flash", 64, 12.5)
    with env.factory() as session:
        first_settings = resolve_turn_settings(session, settings)
    first = _ask(env, first_settings, _fake(failing=True))
    execute_turn(first)

    _save(env, settings, "deepseek", "deepseek-flash", 222, 22)
    with env.factory() as session:
        retry_settings = resolve_turn_settings(session, settings)
    retried = start_retry_turn(
        env.factory,
        retry_settings,
        scope=CaseScope(case_id=env.case_id),
        run_id=first.run_id,
        generator=_fake(),
        embedder=FakeEmbedder(),
        index=env.index,
        token_counter=FakeTokenCounter(),
    )
    with env.factory() as session:
        run = session.get(Run, retried.run_id)
    assert run.generator_provider == "deepseek"
    assert run.generator_max_output_tokens == 222
    assert run.generator_timeout_seconds == 22


def test_counter_limits_and_timeout_follow_the_provider_profile(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    settings = _external(env)
    _save(env, settings, "deepseek", "deepseek-flash", 77, 7.5)
    with env.factory() as session:
        turn = resolve_turn_settings(session, settings)

    counter = build_prompt_counter(turn)
    context = SimpleNamespace(deps=SimpleNamespace(settings=turn), started_perf=time.perf_counter())
    assert counter.describe()["method"] == "estimated"
    assert (
        prompt_limit(turn) == turn.provider_context_window - 77 - turn.context_safety_margin_tokens
    )
    assert _model_timeout(context) == 7.5
