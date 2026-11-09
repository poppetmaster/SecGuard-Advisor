"""Pruebas de la revisión humana del respaldo semántico."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from tests.fixtures.conversation import build_env
from tests.fixtures.fakes import FakeEmbedder, FakeTokenCounter, ScriptedGenerator

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.conversation.llm import AnswerPayload, Claim
from secguard_advisor.conversation.turn import execute_turn, start_question_turn
from secguard_advisor.db.models import Case, MessageCitation
from secguard_advisor.retrieval.review import (
    CitationNotFound,
    ReviewNotAllowed,
    ReviewNotConfigured,
    review_citation,
)


def _answered_turn(env):
    generator = ScriptedGenerator(
        [
            AnswerPayload(
                answer="El marco define seis funciones.",
                claims=[
                    Claim(
                        text="Afirmación",
                        chunk_ids=[env.public_document.chunk_ids[0]],
                        quote="seis funciones centrales",
                    )
                ],
            )
        ]
    )
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
    execute_turn(context)
    return context.run_id


def _citation(env) -> MessageCitation:
    with env.factory() as session:
        return session.scalar(
            select(MessageCitation).where(MessageCitation.check_status == "valid")
        )


def _rejected_turn(env):
    generator = ScriptedGenerator(
        [
            AnswerPayload(
                answer="El marco define seis funciones.",
                claims=[
                    Claim(
                        text="Afirmación",
                        chunk_ids=[env.public_document.chunk_ids[0]],
                        quote="paráfrasis uno",
                    )
                ],
            ),
            AnswerPayload(
                answer="El marco define seis funciones.",
                claims=[
                    Claim(
                        text="Afirmación",
                        chunk_ids=[env.public_document.chunk_ids[0]],
                        quote="paráfrasis dos",
                    )
                ],
            ),
        ]
    )
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
    execute_turn(context)


def test_supported_review_records_author_date_and_note(tmp_path: Path) -> None:
    env = build_env(tmp_path)
    _answered_turn(env)
    citation = _citation(env)

    with env.factory() as session:
        updated = review_citation(
            session,
            CaseScope(case_id=env.case_id),
            message_id=citation.message_id,
            citation_id=citation.id,
            status="supported",
            note="El fragmento sostiene la afirmación.",
            reviewer_name="Revisora Local",
        )
        session.commit()

    assert updated.support_review_status == "supported"
    assert updated.support_reviewed_by == "Revisora Local"
    assert updated.support_reviewed_at
    assert updated.support_review_note == "El fragmento sostiene la afirmación."


def test_not_supported_review_is_recorded(tmp_path: Path) -> None:
    env = build_env(tmp_path)
    _answered_turn(env)
    citation = _citation(env)

    with env.factory() as session:
        updated = review_citation(
            session,
            CaseScope(case_id=env.case_id),
            message_id=citation.message_id,
            citation_id=citation.id,
            status="not_supported",
            note=None,
            reviewer_name="Revisor",
        )
        session.commit()

    assert updated.support_review_status == "not_supported"
    assert updated.support_review_note is None


def test_missing_reviewer_identity_is_rejected(tmp_path: Path) -> None:
    env = build_env(tmp_path)
    _answered_turn(env)
    citation = _citation(env)

    with env.factory() as session:
        with pytest.raises(ReviewNotConfigured):
            review_citation(
                session,
                CaseScope(case_id=env.case_id),
                message_id=citation.message_id,
                citation_id=citation.id,
                status="supported",
                note=None,
                reviewer_name=None,
            )
        session.rollback()

    with env.factory() as session:
        stored = session.get(MessageCitation, citation.id)
        assert stored.support_review_status == "unreviewed"
        assert stored.support_reviewed_by is None


def test_citation_from_another_case_is_not_found(tmp_path: Path) -> None:
    env = build_env(tmp_path)
    _answered_turn(env)
    citation = _citation(env)
    with env.factory() as session:
        other = Case(title="Otro caso", synthetic_notice="Escenario educativo")
        session.add(other)
        session.commit()
        other_id = other.id

    with env.factory() as session, pytest.raises(CitationNotFound):
        review_citation(
            session,
            CaseScope(case_id=other_id),
            message_id=citation.message_id,
            citation_id=citation.id,
            status="supported",
            note=None,
            reviewer_name="Revisor",
        )


def test_rejected_citation_cannot_be_reviewed(tmp_path: Path) -> None:
    env = build_env(tmp_path)
    _rejected_turn(env)
    with env.factory() as session:
        rejected = session.scalar(
            select(MessageCitation).where(MessageCitation.check_status == "rejected")
        )
        assert rejected is not None
        with pytest.raises(ReviewNotAllowed):
            review_citation(
                session,
                CaseScope(case_id=env.case_id),
                message_id=rejected.message_id,
                citation_id=rejected.id,
                status="supported",
                note=None,
                reviewer_name="Revisor",
            )


def test_invalid_status_and_long_note_are_rejected(tmp_path: Path) -> None:
    env = build_env(tmp_path)
    _answered_turn(env)
    citation = _citation(env)

    with env.factory() as session:
        with pytest.raises(ValueError):
            review_citation(
                session,
                CaseScope(case_id=env.case_id),
                message_id=citation.message_id,
                citation_id=citation.id,
                status="approved",
                note=None,
                reviewer_name="Revisor",
            )
        with pytest.raises(ValueError):
            review_citation(
                session,
                CaseScope(case_id=env.case_id),
                message_id=citation.message_id,
                citation_id=citation.id,
                status="supported",
                note="x" * 501,
                reviewer_name="Revisor",
            )


def test_unknown_message_is_not_found(tmp_path: Path) -> None:
    env = build_env(tmp_path)
    _answered_turn(env)
    citation = _citation(env)

    with env.factory() as session, pytest.raises(CitationNotFound):
        review_citation(
            session,
            CaseScope(case_id=env.case_id),
            message_id="0" * 32,
            citation_id=citation.id,
            status="supported",
            note=None,
            reviewer_name="Revisor",
        )
