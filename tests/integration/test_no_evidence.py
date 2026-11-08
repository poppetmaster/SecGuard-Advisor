"""Integración real: la ausencia de evidencia se declara sin inventar citas."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select
from tests.fixtures.corpus import create_case
from tests.fixtures.real_corpus import real_embedder

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.conversation.llm import GenerationConfig, OllamaGenerator
from secguard_advisor.conversation.turn import execute_turn, start_question_turn
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import Message, MessageCitation, Run
from secguard_advisor.retrieval.index import ChromaIndex

pytestmark = pytest.mark.integration

QUESTION = "¿Cuál es la receta tradicional de la tortilla de patatas?"


def test_off_domain_question_abstains_without_citations(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, storage_dir=tmp_path / "storage")
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)

    with factory() as session:
        case_id = create_case(session, "Caso sin evidencia")
        session.commit()

    generator = OllamaGenerator(
        GenerationConfig(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            num_ctx=settings.generator_num_ctx,
            temperature=settings.generator_temperature,
            seed=settings.generator_seed,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    )
    embedder = real_embedder(settings)
    index = ChromaIndex(settings.chroma_dir)
    try:
        context = start_question_turn(
            factory,
            settings,
            scope=CaseScope(case_id=case_id),
            question=QUESTION,
            generator=generator,
            embedder=embedder,
            index=index,
        )
        result = execute_turn(context)

        assert result.status == "succeeded"
        assert result.outcome == "insufficient_evidence"

        with factory() as session:
            run = session.scalar(select(Run).where(Run.case_id == case_id))
            assert run is not None
            assert run.outcome == "insufficient_evidence"
            assert session.scalar(select(func.count()).select_from(MessageCitation)) == 0
            answer = session.scalar(select(Message).where(Message.role == "assistant"))
            assert answer is not None
            assert "No encontré evidencia documental suficiente" in answer.content
    finally:
        embedder.close()
        engine.dispose()
