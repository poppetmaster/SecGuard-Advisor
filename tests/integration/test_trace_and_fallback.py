"""Traza real, traza desactivada y caída controlada de LangSmith."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from tests.fixtures.conversation import build_env
from tests.fixtures.fakes import FakeEmbedder, FakeTokenCounter, ScriptedGenerator

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.conversation.llm import AnswerPayload
from secguard_advisor.conversation.turn import execute_turn, start_question_turn
from secguard_advisor.db.models import Run

pytestmark = pytest.mark.integration


def _ask(env, generator):
    context = start_question_turn(
        env.factory,
        env.settings,
        scope=CaseScope(case_id=env.case_id),
        question="¿Qué controles aplican?",
        generator=generator,
        embedder=FakeEmbedder(),
        index=env.index,
        token_counter=FakeTokenCounter(),
    )
    return context, execute_turn(context)


def _trace(env, run_id: str) -> tuple[str, str | None, str | None]:
    with env.factory() as session:
        run = session.get(Run, run_id)
        return run.trace_status, run.trace_id, run.trace_url


def test_disabled_trace_keeps_the_local_query_complete(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    generator = ScriptedGenerator([AnswerPayload(answer="respuesta local", claims=[])])

    context, result = _ask(env, generator)

    assert result.status == "succeeded"
    assert _trace(env, context.run_id) == ("disabled", None, None)
    with env.factory() as session:
        run = session.get(Run, context.run_id)
        assert run.answer_message_id is not None


def test_langsmith_failure_keeps_the_local_query_complete(tmp_path: Path, monkeypatch) -> None:
    real = Settings()
    env = build_env(
        tmp_path,
        with_documents=False,
        min_score=-1.0,
        settings_overrides={
            "langsmith_tracing": True,
            "langsmith_api_key": "lsv2_decoy_key",
            "langsmith_project": real.langsmith_project,
            "langsmith_endpoint": real.langsmith_endpoint,
        },
    )

    def broken_client(**_kwargs):
        raise RuntimeError("langsmith caído")

    monkeypatch.setattr("secguard_advisor.evidence.tracing._default_client", broken_client)
    generator = ScriptedGenerator([AnswerPayload(answer="respuesta local", claims=[])])

    context, result = _ask(env, generator)

    assert result.status == "succeeded"
    assert _trace(env, context.run_id)[0] == "failed"


def test_real_submission_marks_submitted_without_confirming(tmp_path: Path) -> None:
    real = Settings()
    if not real.langsmith_tracing or real.langsmith_api_key is None:
        pytest.skip("LangSmith no configurado; el envío real queda pendiente")

    env = build_env(
        tmp_path,
        with_documents=False,
        min_score=-1.0,
        settings_overrides={
            "langsmith_tracing": True,
            "langsmith_api_key": real.langsmith_api_key.get_secret_value(),
            "langsmith_project": real.langsmith_project,
            "langsmith_endpoint": real.langsmith_endpoint,
        },
    )
    generator = ScriptedGenerator([AnswerPayload(answer="respuesta sintética", claims=[])])

    context, result = _ask(env, generator)

    assert result.status == "succeeded"
    status, trace_id, trace_url = _trace(env, context.run_id)
    assert status == "submitted"
    assert trace_id
    assert trace_url
    assert "trace" in trace_url
    with env.factory() as session:
        run = session.scalar(select(Run).where(Run.id == context.run_id))
        assert run.trace_status != "confirmed"
