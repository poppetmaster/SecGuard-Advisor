"""Pruebas de las rutas del grafo conversacional."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from tests.fixtures.conversation import build_env
from tests.fixtures.fakes import FakeEmbedder, ScriptedGenerator

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.conversation.llm import AnswerPayload, Claim
from secguard_advisor.conversation.turn import execute_turn, start_question_turn
from secguard_advisor.db.models import Message, MessageCitation, Run, RunStep


def _claim(chunk_id: str, quote: str, text: str = "Afirmación documentada.") -> Claim:
    return Claim(text=text, chunk_ids=[chunk_id], quote=quote)


def _run(env, generator, question: str = "¿Qué controles aplican?"):
    scope = CaseScope(case_id=env.case_id)
    context = start_question_turn(
        env.factory,
        env.settings,
        scope=scope,
        question=question,
        generator=generator,
        embedder=FakeEmbedder(),
        index=env.index,
    )
    return execute_turn(context)


def _count(env, model) -> int:
    with env.factory() as session:
        return len(list(session.scalars(select(model))))


def test_valid_first_attempt_goes_straight_to_persist(tmp_path: Path) -> None:
    env = build_env(tmp_path)
    generator = ScriptedGenerator(
        [
            AnswerPayload(
                answer="El marco define seis funciones.",
                claims=[_claim(env.public_document.chunk_ids[0], "seis funciones centrales")],
            )
        ]
    )

    result = _run(env, generator)

    assert result.status == "succeeded"
    assert result.outcome == "answered"
    assert generator.calls == 1
    with env.factory() as session:
        run = session.scalar(select(Run).where(Run.case_id == env.case_id))
        assert run.status == "succeeded"
        assert run.steps_count == 5
        names = [
            step.name
            for step in session.scalars(
                select(RunStep).where(RunStep.run_id == run.id).order_by(RunStep.seq)
            )
        ]
        assert names == ["load_scope", "retrieve", "agent", "validate", "persist"]


def test_invalid_then_repaired_stops_after_one_repair(tmp_path: Path) -> None:
    env = build_env(tmp_path)
    generator = ScriptedGenerator(
        [
            AnswerPayload(
                answer="El marco define seis funciones.",
                claims=[_claim(env.public_document.chunk_ids[0], "texto parafraseado")],
            ),
            AnswerPayload(
                answer="El marco define seis funciones.",
                claims=[_claim(env.public_document.chunk_ids[0], "seis funciones centrales")],
            ),
        ]
    )

    result = _run(env, generator)

    assert result.outcome == "answered"
    assert generator.calls == 2
    assert "no superó el control automático" in generator.prompts[-1]
    with env.factory() as session:
        citations = list(session.scalars(select(MessageCitation)))
        assert [citation.check_status for citation in citations] == ["valid"]


def test_two_invalid_attempts_abstain_without_citations(tmp_path: Path) -> None:
    env = build_env(tmp_path)
    generator = ScriptedGenerator(
        [
            AnswerPayload(
                answer="El marco define seis funciones.",
                claims=[_claim(env.public_document.chunk_ids[0], "paráfrasis uno")],
            ),
            AnswerPayload(
                answer="El marco define seis funciones.",
                claims=[_claim(env.public_document.chunk_ids[0], "paráfrasis dos")],
            ),
        ]
    )

    result = _run(env, generator)

    assert result.outcome == "abstained_invalid_citations"
    assert generator.calls == 2
    with env.factory() as session:
        citations = list(session.scalars(select(MessageCitation)))
        assert citations and all(citation.check_status == "rejected" for citation in citations)
        answer = session.scalar(select(Message).where(Message.role == "assistant"))
        assert answer is not None
        assert "no pudo sostenerse con citas verificables" in answer.content


def test_answer_without_claims_abstains(tmp_path: Path) -> None:
    env = build_env(tmp_path)
    generator = ScriptedGenerator([AnswerPayload(answer="Respuesta sin respaldo.", claims=[])])

    result = _run(env, generator)

    assert result.outcome == "abstained_invalid_citations"
    assert generator.calls == 2
    assert _count(env, Message) == 2
