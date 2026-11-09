"""Integración real: el modelo solicita findings_query y las cifras coinciden con SQLite."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import func, select
from tests.fixtures.real_corpus import real_embedder

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.conversation.llm import GenerationConfig, OllamaGenerator
from secguard_advisor.conversation.memory import open_memory
from secguard_advisor.conversation.tokenizer import load_prompt_counter
from secguard_advisor.conversation.turn import execute_turn, start_question_turn
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import Asset, Finding, Message, Run, RunStep, RunToolCall
from secguard_advisor.retrieval.index import ChromaIndex
from secguard_advisor.seed.demo import seed_demo

pytestmark = pytest.mark.integration

QUESTION = (
    "¿Cuántos hallazgos de severidad High están registrados en este caso? Agrúpalos por activo."
)


def test_model_requests_the_tool_and_counts_match_sqlite(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        storage_dir=tmp_path / "storage",
        corpus_dir=tmp_path / "corpus",
    )
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        report = seed_demo(session)
        session.commit()
        case_id = report.case_id
        expected_total = session.scalar(
            select(func.count())
            .select_from(Finding)
            .where(Finding.case_id == case_id, Finding.severity_label == "High")
        )
        expected_groups = dict(
            session.execute(
                select(Asset.name, func.count())
                .select_from(Finding)
                .join(Asset, Finding.asset_id == Asset.id)
                .where(Finding.case_id == case_id, Finding.severity_label == "High")
                .group_by(Asset.name)
            ).all()
        )
    assert expected_total == 4

    store = open_memory(settings.checkpoints_path)
    embedder = real_embedder(settings)
    index = ChromaIndex(settings.chroma_dir)
    try:
        generator = OllamaGenerator(
            GenerationConfig(
                base_url=settings.ollama_base_url,
                model=settings.ollama_model,
                num_ctx=settings.generator_num_ctx,
                num_predict=settings.generator_num_predict,
                temperature=settings.generator_temperature,
                seed=settings.generator_seed,
                timeout_seconds=settings.llm_timeout_seconds,
            )
        )
        context = start_question_turn(
            factory,
            settings,
            scope=CaseScope(case_id=case_id),
            question=QUESTION,
            generator=generator,
            embedder=embedder,
            index=index,
            token_counter=load_prompt_counter(settings.ollama_model),
        )
        result = execute_turn(context, memory=store)

        assert result.status == "succeeded"
        assert result.outcome == "answered", "el modelo no respondió con la herramienta"
        with factory() as session:
            run = session.get(Run, context.run_id)
            assert 1 <= run.tool_calls_count <= 2
            calls = list(
                session.scalars(
                    select(RunToolCall)
                    .where(RunToolCall.run_id == run.id)
                    .order_by(RunToolCall.seq)
                )
            )
            call = calls[0]
            assert call is not None
            assert call.origin == "model_requested"
            assert call.status == "ok"
            arguments = json.loads(call.arguments_json)
            assert arguments.get("severity") == "High"
            assert arguments.get("group_by") == "asset"
            summary = json.loads(call.result_summary_json)
            assert summary["total"] == expected_total
            assert {group["key"]: group["count"] for group in summary["groups"]} == (
                expected_groups
            )
            answer = session.scalar(
                select(Message.content).where(Message.id == run.answer_message_id)
            )
            assert "4" in answer
            assert "api-gateway" in answer.casefold()
            steps = list(
                session.scalars(
                    select(RunStep)
                    .where(RunStep.run_id == run.id, RunStep.name == "agent")
                    .order_by(RunStep.seq)
                )
            )
            assert len(steps) >= 1
            for step in steps:
                detail = json.loads(step.detail_json)
                assert detail["admitted_tokens"] <= detail["limit"]
                if detail.get("observed_prompt_tokens") is not None:
                    assert detail["observed_prompt_tokens"] <= detail["admitted_tokens"]
            print(
                "herramienta:",
                {
                    "arguments": arguments,
                    "total": summary["total"],
                    "groups": summary["groups"],
                    "sqlite_total": expected_total,
                    "sqlite_groups": expected_groups,
                    "steps": [
                        {
                            "admitted": json.loads(step.detail_json)["admitted_tokens"],
                            "observed": json.loads(step.detail_json).get("observed_prompt_tokens"),
                        }
                        for step in steps
                    ],
                },
            )
    finally:
        store.close()
        embedder.close()
        engine.dispose()
