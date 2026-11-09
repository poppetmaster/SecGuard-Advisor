"""Integración real: la estimación es conservadora frente a Qwen3.5."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from tests.fixtures.corpus import create_case
from tests.fixtures.real_corpus import real_embedder

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.conversation.budget import plan_prompt
from secguard_advisor.conversation.llm import GenerationConfig, OllamaGenerator
from secguard_advisor.conversation.memory import HistoryTurn
from secguard_advisor.corpus.ingest import ingest_public_corpus
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.retrieval.index import ChromaIndex
from secguard_advisor.retrieval.search import search_documents

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]
QUESTION = "¿Cuáles son las seis funciones centrales del NIST Cybersecurity Framework 2.0?"


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        storage_dir=tmp_path / "storage",
        corpus_dir=tmp_path / "corpus",
    )


def _ingest_csf2(settings: Settings, factory) -> None:
    source = ROOT / "data" / "corpus" / "originals" / "csf2.pdf"
    manifest = json.loads((ROOT / "data" / "corpus" / "manifest.json").read_text("utf-8"))
    entry = next(item for item in manifest["sources"] if item["id"] == "csf2")
    originals = settings.corpus_dir / "originals"
    originals.mkdir(parents=True, exist_ok=True)
    shutil.copy(source, originals / "csf2.pdf")
    (settings.corpus_dir / "manifest.json").write_text(
        json.dumps({"schema_version": 1, "sources": [entry]}), encoding="utf-8"
    )
    embedder = real_embedder(settings)
    index = ChromaIndex(settings.chroma_dir)
    try:
        outcomes = ingest_public_corpus(factory, settings, embedder=embedder, index=index)
    finally:
        embedder.close()
    assert [outcome.status for outcome in outcomes] == ["created"]


def _history(pairs: int, size: int) -> tuple[HistoryTurn, ...]:
    turns: list[HistoryTurn] = []
    seq = 1
    for index in range(1, pairs + 1):
        turns.append(HistoryTurn(seq, "user", f"pregunta {index} " + "q" * size))
        seq += 1
        turns.append(HistoryTurn(seq, "assistant", f"respuesta {index} " + "a" * size))
        seq += 1
    return tuple(turns)


def test_estimate_is_conservative_with_the_real_generator(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        case_id = create_case(session, "Presupuesto real")
        session.commit()
    _ingest_csf2(settings, factory)

    embedder = real_embedder(settings)
    index = ChromaIndex(settings.chroma_dir)
    try:
        with factory() as session:
            retrieval = search_documents(
                session,
                scope=CaseScope(case_id=case_id),
                query=QUESTION,
                embedder=embedder,
                index=index,
                top_k=settings.retrieval_top_k,
                min_score=settings.retrieval_min_score,
                token_budget=settings.retrieval_token_budget,
            )
        assert retrieval.hits

        plan = plan_prompt(
            question=QUESTION,
            hits=retrieval.hits,
            history=_history(4, 900),
            settings=settings,
        )
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
        payload = generator.generate(system=plan.system, user=plan.user)

        assert payload.answer is not None
        assert generator.last_usage is not None
        observed = generator.last_usage["prompt_tokens"]
        assert observed is not None
        assert observed <= plan.estimated_prompt_tokens, (
            "la estimación debe ser una cota conservadora del prompt real"
        )
        assert observed + settings.generator_num_predict <= settings.generator_num_ctx
        print(
            "presupuesto:",
            {
                "estimated": plan.estimated_prompt_tokens,
                "observed": observed,
                "limit": plan.prompt_limit,
                "output_reserve": settings.generator_num_predict,
                "safety_margin": settings.context_safety_margin_tokens,
                "dropped_history_messages": plan.dropped_history_messages,
                "dropped_sources": plan.dropped_sources,
                "observed_bytes_per_token": round(
                    len(plan.user.encode("utf-8")) / max(observed, 1), 2
                ),
            },
        )
    finally:
        embedder.close()
        engine.dispose()
