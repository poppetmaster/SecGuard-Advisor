"""Persistencia de uso/costo externo por llamada (Entrega 2)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from tests.fixtures.conversation import build_env
from tests.fixtures.fakes import FakeEmbedder, FakeTokenCounter, ScriptedGenerator

from secguard_advisor.cases.external import authorize_case
from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.conversation.llm import AnswerPayload, ModelUnavailable, ToolDecision
from secguard_advisor.conversation.turn import execute_turn, start_question_turn
from secguard_advisor.db.models import ProviderBudgetLedger, ProviderUsage, Run


def _settings(env) -> Settings:
    return Settings(
        _env_file=None,
        storage_dir=env.settings.storage_dir,
        generation_provider="deepseek",
        generation_model="deepseek-flash",
        deepseek_api_key="secret",
        external_budget_usd=Decimal("1"),
        external_run_budget_usd=Decimal("1"),
    )


def _generator(usage: dict | None) -> ScriptedGenerator:
    generator = ScriptedGenerator(
        payloads=[AnswerPayload(answer="respuesta", claims=[])],
        decisions=[ToolDecision(use_findings=False, arguments={})],
    )
    generator.provider = "deepseek"
    generator.model = "deepseek-flash"
    generator.identity = "deepseek-flash"
    generator.last_usage = usage
    return generator


def _ask(env, settings, generator):
    context = start_question_turn(
        env.factory,
        settings,
        scope=CaseScope(case_id=env.case_id),
        question="¿Qué controles aplican?",
        generator=generator,
        embedder=FakeEmbedder(),
        index=env.index,
        token_counter=FakeTokenCounter(),
    )
    return context, execute_turn(context)


def test_observed_usage_is_persisted_with_cost(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    settings = _settings(env)
    generator = _generator(
        {
            "input_tokens": 100,
            "output_tokens": 20,
            "cached_tokens": 0,
            "cache_write_tokens": 0,
            "source": "observed",
        }
    )
    # Authorize before start (the helper authorizes after; do it here explicitly).
    with env.factory() as session:
        authorize_case(
            session, case_id=env.case_id, scope="fictional_case", authorized_by="Revisora"
        )
        session.commit()

    context, result = _ask(env, settings, generator)

    assert result.status == "succeeded"
    with env.factory() as session:
        rows = list(
            session.scalars(select(ProviderUsage).where(ProviderUsage.run_id == context.run_id))
        )
        run = session.get(Run, context.run_id)
    assert rows
    assert all(row.cost_status == "calculated" for row in rows)
    assert run.usage_input_tokens and run.usage_input_tokens > 0
    assert run.cost_status == "calculated"
    assert run.cost_usd is not None


def test_missing_usage_is_persisted_as_unknown(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    settings = _settings(env)
    generator = _generator(None)
    with env.factory() as session:
        authorize_case(
            session, case_id=env.case_id, scope="fictional_case", authorized_by="Revisora"
        )
        session.commit()

    context, result = _ask(env, settings, generator)

    assert result.status == "succeeded"
    with env.factory() as session:
        rows = list(
            session.scalars(select(ProviderUsage).where(ProviderUsage.run_id == context.run_id))
        )
        run = session.get(Run, context.run_id)
    assert rows
    assert all(row.cost_status == "unknown" for row in rows)
    assert run.cost_status == "unknown"
    assert run.cost_usd is None


def test_failed_external_call_keeps_the_reserved_budget(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    settings = _settings(env)
    generator = ScriptedGenerator(error=ModelUnavailable("caído"))
    generator.provider = "deepseek"
    generator.model = "deepseek-flash"
    generator.identity = "deepseek-flash"
    generator.last_usage = None
    with env.factory() as session:
        authorize_case(
            session, case_id=env.case_id, scope="fictional_case", authorized_by="Revisora"
        )
        session.commit()

    context, result = _ask(env, settings, generator)

    assert result.status == "failed"
    assert result.http_status == 503
    with env.factory() as session:
        ledger = session.scalar(
            select(ProviderBudgetLedger).where(ProviderBudgetLedger.run_id == context.run_id)
        )
        usage = session.scalar(select(ProviderUsage).where(ProviderUsage.run_id == context.run_id))
        run = session.get(Run, context.run_id)
    assert ledger.state == "reconciled"
    assert ledger.settled_usd == ledger.reserved_usd
    assert usage.cost_status == "unknown"
    assert run.cost_status == "unknown"
