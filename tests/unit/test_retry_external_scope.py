"""Reintento externo: autorización, alcance, evidencia y cero llamadas (R1/R3)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from tests.fixtures.conversation import CASE_TEXT, build_env
from tests.fixtures.fakes import FakeEmbedder, FakeTokenCounter, ScriptedGenerator
from tests.fixtures.findings import seed_findings

from secguard_advisor.cases.external import (
    ExternalProcessingBlocked,
    authorize_case,
    revoke_case,
)
from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.conversation.llm import AnswerPayload, ModelUnavailable, ToolDecision
from secguard_advisor.conversation.retry import start_retry_turn
from secguard_advisor.conversation.turn import execute_turn, start_question_turn
from secguard_advisor.db.models import Message, Run, RunToolCall
from secguard_advisor.web.app import create_app


class _ExplodingCounter:
    def count(self, system: str, user: str) -> int:
        raise AssertionError("no debe contarse un prompt externo sin autorización")

    def describe(self) -> dict:
        return {"method": "fake"}


class _ExplodingGenerator:
    provider = "deepseek"
    model = "deepseek-flash"
    identity = None
    last_usage = None

    def decide(self, **_kwargs):
        raise AssertionError("no debe llamarse al modelo sin autorización")

    def generate(self, **_kwargs):
        raise AssertionError("no debe llamarse al modelo sin autorización")

    def close(self) -> None:
        return None


def _external(env, *, budget: str = "1") -> Settings:
    return Settings(
        _env_file=None,
        storage_dir=env.settings.storage_dir,
        generation_provider="deepseek",
        generation_model="deepseek-flash",
        generation_max_output_tokens=64,
        generation_timeout_seconds=12.5,
        deepseek_api_key="secret",
        external_budget_usd=Decimal(budget),
        external_run_budget_usd=Decimal(budget),
    )


def _fake(*, failing: bool = False) -> ScriptedGenerator:
    generator = ScriptedGenerator(
        payloads=[AnswerPayload(answer="respuesta", claims=[])],
        decisions=[ToolDecision(use_findings=False, arguments={})],
        error=ModelUnavailable("caído") if failing else None,
    )
    generator.provider = "deepseek"
    generator.model = "deepseek-flash"
    generator.identity = "deepseek-flash"
    generator.last_usage = {
        "input_tokens": 100,
        "output_tokens": 20,
        "cached_tokens": 0,
        "cache_write_tokens": 0,
        "source": "observed",
    }
    return generator


def _authorize(env, scope: str) -> None:
    with env.factory() as session:
        authorize_case(session, case_id=env.case_id, scope=scope, authorized_by="Revisora")
        session.commit()


def _start(env, settings, generator, question: str = "¿Qué controles aplican?"):
    return start_question_turn(
        env.factory,
        settings,
        scope=CaseScope(case_id=env.case_id),
        question=question,
        generator=generator,
        embedder=FakeEmbedder(),
        index=env.index,
        token_counter=FakeTokenCounter(),
    )


def _retry(env, settings, generator, run_id: str, token_counter=None):
    return start_retry_turn(
        env.factory,
        settings,
        scope=CaseScope(case_id=env.case_id),
        run_id=run_id,
        generator=generator,
        embedder=FakeEmbedder(),
        index=env.index,
        token_counter=token_counter or FakeTokenCounter(),
    )


def test_retry_without_authorization_makes_zero_calls(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    _authorize(env, "fictional_case")
    settings = _external(env)
    first = _start(env, settings, _fake(failing=True))
    execute_turn(first)
    with env.factory() as session:
        revoke_case(session, case_id=env.case_id)
        session.commit()

    with pytest.raises(ExternalProcessingBlocked):
        _retry(
            env,
            settings,
            _ExplodingGenerator(),
            first.run_id,
            token_counter=_ExplodingCounter(),
        )


def test_retry_uses_public_scope_and_excludes_private_content(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=True)
    _authorize(env, "public_corpus")
    settings = _external(env)
    first = _start(env, settings, _fake(), "¿Cuál es la primera pregunta privada?")
    execute_turn(first)
    second = _start(env, settings, _fake(failing=True), "¿Cuál es la segunda pregunta?")
    execute_turn(second)

    generator = _fake()
    retried = _retry(env, settings, generator, second.run_id)
    result = execute_turn(retried)

    assert result.status == "succeeded"
    assert retried.external_scope == "public_corpus"
    assert retried.case_context is None
    assert CASE_TEXT not in generator.prompts[-1]
    assert "¿Cuál es la primera pregunta privada?" not in generator.prompts[-1]


def test_retry_records_effective_profile_and_keeps_history(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    _authorize(env, "fictional_case")
    settings = _external(env)
    first = _start(env, settings, _fake(failing=True))
    execute_turn(first)

    retried = _retry(env, settings, _fake(), first.run_id)
    with env.factory() as session:
        run = session.get(Run, retried.run_id)
        original = session.get(Run, first.run_id)
        questions = session.scalar(
            select(func.count())
            .select_from(Message)
            .where(Message.conversation_id == retried.conversation_id, Message.role == "user")
        )
    assert run.generator_provider == "deepseek"
    assert run.generator_model == "deepseek-flash"
    assert run.generator_identity == "deepseek-flash"
    assert run.generator_max_output_tokens == 64
    assert run.generator_timeout_seconds == 12.5
    assert run.external_authorization_id is not None
    assert run.attempt_no == 2
    assert run.retry_of_run_id == first.run_id
    assert questions == 1
    assert original.generator_max_output_tokens == 64
    app = create_app(settings, ollama_probe=lambda: True, token_counter=FakeTokenCounter())
    with TestClient(app) as client:
        page = client.get(f"/cases/{env.case_id}/runs/{retried.run_id}")
    assert page.status_code == 200
    assert "deepseek" in page.text
    assert "64 tokens" in page.text
    assert "12.5 s" in page.text


def test_change_from_local_to_external_on_retry(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    local = ScriptedGenerator(error=ModelUnavailable("caído"))
    first = _start(env, env.settings, local)
    execute_turn(first)
    _authorize(env, "fictional_case")

    retried = _retry(env, _external(env), _fake(), first.run_id)
    with env.factory() as session:
        original = session.get(Run, first.run_id)
        new = session.get(Run, retried.run_id)
    assert retried.external_scope == "fictional_case"
    assert new.generator_provider == "deepseek"
    assert new.generator_max_output_tokens == 64
    assert new.generator_timeout_seconds == 12.5
    assert original.generator_provider == "ollama"
    assert original.generator_max_output_tokens == 1200
    assert original.generator_timeout_seconds == 90.0


def test_imported_findings_are_blocked_on_retry(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    seed_findings(env.factory, case_id=env.case_id, findings=[("api", "High", "900001", [])])
    _authorize(env, "fictional_case")
    settings = _external(env)
    first = _start(env, settings, _fake(failing=True))
    execute_turn(first)
    generator = _fake()
    generator.decisions = [ToolDecision(use_findings=True, arguments={"origin": "imported"})]

    retried = _retry(env, settings, generator, first.run_id)
    result = execute_turn(retried)

    assert result.http_status == 403
    assert result.error_code == "external_tool_blocked"
    with env.factory() as session:
        assert (
            session.scalar(select(RunToolCall).where(RunToolCall.run_id == retried.run_id)) is None
        )


def test_start_records_effective_profile_and_view(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    _authorize(env, "fictional_case")
    settings = _external(env)

    context = _start(env, settings, _fake())
    with env.factory() as session:
        run = session.get(Run, context.run_id)
    assert run.generator_provider == "deepseek"
    assert run.generator_model == "deepseek-flash"
    assert run.generator_identity == "deepseek-flash"
    assert run.generator_max_output_tokens == 64
    assert run.generator_timeout_seconds == 12.5
    assert run.external_authorization_id is not None

    app = create_app(settings, ollama_probe=lambda: True, token_counter=FakeTokenCounter())
    with TestClient(app) as client:
        page = client.get(f"/cases/{env.case_id}/runs/{context.run_id}")
    assert page.status_code == 200
    assert "deepseek" in page.text
    assert "64 tokens" in page.text
    assert "12.5 s" in page.text
