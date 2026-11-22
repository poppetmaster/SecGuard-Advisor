"""Reglas de findings_query con proveedor externo (Entrega 2)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select
from tests.fixtures.conversation import CASE_TEXT, build_env
from tests.fixtures.fakes import FakeEmbedder, FakeTokenCounter, ScriptedGenerator
from tests.fixtures.findings import seed_findings

from secguard_advisor.cases.external import ExternalProcessingBlocked, authorize_case
from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.conversation.llm import AnswerPayload, ToolDecision
from secguard_advisor.conversation.turn import execute_turn, start_question_turn
from secguard_advisor.db.models import ProviderUsage, RunToolCall


def _external_settings(env, *, budget: str = "1") -> Settings:
    return Settings(
        _env_file=None,
        storage_dir=env.settings.storage_dir,
        generation_provider="deepseek",
        generation_model="deepseek-flash",
        deepseek_api_key="secret",
        external_budget_usd=Decimal(budget),
        external_run_budget_usd=Decimal(budget),
    )


def _generator(*decisions) -> ScriptedGenerator:
    generator = ScriptedGenerator(
        payloads=[AnswerPayload(answer="Hay 1 hallazgo High.", claims=[])],
        decisions=list(decisions),
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
        authorize_case(
            session,
            case_id=env.case_id,
            scope=scope,
            authorized_by="Revisora",
        )
        session.commit()


def _ask(env, settings, generator, question: str):
    context = start_question_turn(
        env.factory,
        settings,
        scope=CaseScope(case_id=env.case_id),
        question=question,
        generator=generator,
        embedder=FakeEmbedder(),
        index=env.index,
        token_counter=FakeTokenCounter(),
    )
    return context, execute_turn(context)


def test_imported_findings_are_blocked_before_the_tool(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    seed_findings(env.factory, case_id=env.case_id, findings=[("api", "High", "900001", [])])
    _authorize(env, "fictional_case")
    generator = _generator(
        ToolDecision(use_findings=True, arguments={"origin": "imported"}),
    )

    context, result = _ask(env, _external_settings(env), generator, "¿Cuántos High?")

    assert result.status == "failed"
    assert result.http_status == 403
    assert result.error_code == "external_tool_blocked"
    with env.factory() as session:
        assert (
            session.scalar(select(RunToolCall).where(RunToolCall.run_id == context.run_id)) is None
        )
        assert session.scalar(select(ProviderUsage).where(ProviderUsage.run_id == context.run_id))


def test_synthetic_findings_are_allowed_in_a_fictional_case(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    seed_findings(env.factory, case_id=env.case_id, findings=[("api", "High", "900001", [])])
    _authorize(env, "fictional_case")
    generator = _generator(
        ToolDecision(
            use_findings=True,
            arguments={"origin": "synthetic", "severity": "High", "group_by": "asset"},
        ),
        ToolDecision(use_findings=False, arguments={}),
    )

    context, result = _ask(env, _external_settings(env), generator, "¿Cuántos High?")

    assert result.status == "succeeded"
    assert result.outcome == "answered"
    with env.factory() as session:
        call = session.scalar(select(RunToolCall).where(RunToolCall.run_id == context.run_id))
    assert call.status == "ok"
    assert call.origin == "model_requested"


def test_public_corpus_scope_drops_case_evidence_from_the_prompt(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=True)
    _authorize(env, "public_corpus")
    generator = _generator(ToolDecision(use_findings=False, arguments={}))

    _, result = _ask(env, _external_settings(env), generator, "¿Qué controles aplican?")

    assert result.status == "succeeded"
    assert generator.prompts
    assert CASE_TEXT not in generator.prompts[0]


def test_no_authorization_makes_zero_model_calls(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    generator = _generator()

    with pytest.raises(ExternalProcessingBlocked):
        _ask(env, _external_settings(env), generator, "¿Qué controles aplican?")

    assert generator.decision_calls == 0
    assert generator.calls == 0


def test_zero_budget_blocks_before_the_model_call(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    _authorize(env, "fictional_case")
    generator = _generator()

    _, result = _ask(env, _external_settings(env, budget="0"), generator, "¿Qué controles aplican?")

    assert result.status == "failed"
    assert result.http_status == 402
    assert result.error_code == "budget_exceeded"
    assert generator.decision_calls == 0
    assert generator.calls == 0


def test_public_corpus_scope_does_not_send_prior_history(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=True)
    _authorize(env, "public_corpus")
    settings = _external_settings(env)
    generator = _generator(
        ToolDecision(use_findings=False, arguments={}),
        ToolDecision(use_findings=False, arguments={}),
    )

    first_question = "¿Cuál es la primera pregunta privada?"
    second_question = "¿Cuál es la segunda pregunta?"
    _ask(env, settings, generator, first_question)
    _ask(env, settings, generator, second_question)

    assert len(generator.prompts) >= 2
    assert first_question not in generator.prompts[-1]
