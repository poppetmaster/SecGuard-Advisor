"""Pruebas de abstención y distinción de la falta de evidencia."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select
from tests.fixtures.conversation import build_env
from tests.fixtures.fakes import FakeEmbedder, FakeTokenCounter, ScriptedGenerator

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.conversation.llm import AnswerPayload, Claim
from secguard_advisor.conversation.nodes import (
    ABSTAINED_CITATIONS_TEXT,
    INSUFFICIENT_EVIDENCE_TEXT,
)
from secguard_advisor.conversation.turn import execute_turn, start_question_turn
from secguard_advisor.db.models import (
    Message,
    MessageCitation,
    Run,
    RunToolCall,
)


def _turn(env, generator, question: str = "¿Qué exige la norma?"):
    context = start_question_turn(
        env.factory,
        env.settings,
        scope=CaseScope(case_id=env.case_id),
        question=question,
        generator=generator,
        embedder=FakeEmbedder(),
        index=env.index,
        token_counter=FakeTokenCounter(),
    )
    return execute_turn(context)


def test_no_documents_declares_insufficient_evidence(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False)
    generator = ScriptedGenerator(
        [AnswerPayload(answer="Según mi conocimiento general...", claims=[])]
    )

    result = _turn(env, generator)

    assert result.status == "succeeded"
    assert result.outcome == "insufficient_evidence"
    with env.factory() as session:
        run = session.scalar(select(Run).where(Run.case_id == env.case_id))
        assert run.status == "succeeded"
        assert run.outcome == "insufficient_evidence"
        assert session.scalar(select(func.count()).select_from(MessageCitation)) == 0
        assert session.scalar(select(func.count()).select_from(RunToolCall)) == 0
        answer = session.scalar(select(Message).where(Message.role == "assistant"))
        assert answer is not None
        assert "No encontré evidencia documental suficiente" in answer.content
        assert answer.content == INSUFFICIENT_EVIDENCE_TEXT


def test_weak_candidates_without_valid_citations_abstain(tmp_path: Path) -> None:
    env = build_env(tmp_path)
    generator = ScriptedGenerator(
        [
            AnswerPayload(
                answer="El marco define seis funciones.",
                claims=[Claim(text="Afirmación", chunk_ids=[], quote="")],
            )
        ]
    )

    result = _turn(env, generator)

    assert result.outcome == "abstained_invalid_citations"
    with env.factory() as session:
        assert session.scalar(select(func.count()).select_from(MessageCitation)) == 0
        answer = session.scalar(select(Message).where(Message.role == "assistant"))
        assert answer is not None
        assert answer.content == ABSTAINED_CITATIONS_TEXT
        assert answer.content != INSUFFICIENT_EVIDENCE_TEXT


def test_abstention_never_claims_documentary_support(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False)
    generator = ScriptedGenerator([AnswerPayload(answer="Respuesta inventada", claims=[])])

    result = _turn(env, generator)

    assert result.outcome != "answered"
    with env.factory() as session:
        citations = list(session.scalars(select(MessageCitation)))
        assert citations == []
        run = session.scalar(select(Run).where(Run.case_id == env.case_id))
        assert run.outcome == "insufficient_evidence"
