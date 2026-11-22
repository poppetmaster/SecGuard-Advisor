"""Autorización externa por caso (Entrega 2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select

from secguard_advisor.cases.external import (
    ExternalProcessingBlocked,
    active_authorization,
    authorize_case,
    ensure_external_allowed,
    revoke_case,
)
from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import Case, ExternalProcessingAuthorization


def _env(tmp_path: Path):
    settings = Settings(_env_file=None, storage_dir=tmp_path / "storage")
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        case = Case(title="Caso ficticio", synthetic_notice="Escenario sintético.")
        session.add(case)
        session.commit()
        case_id = case.id
    return factory, case_id


def test_credential_alone_does_not_authorize(tmp_path: Path) -> None:
    factory, case_id = _env(tmp_path)

    with factory() as session, pytest.raises(ExternalProcessingBlocked):
        ensure_external_allowed(session, case_id=case_id, provider="deepseek")


def test_authorize_and_revoke_public_corpus(tmp_path: Path) -> None:
    factory, case_id = _env(tmp_path)

    with factory() as session:
        authorization = authorize_case(
            session,
            case_id=case_id,
            scope="public_corpus",
            authorized_by="Revisora",
        )
        session.commit()
        assert authorization.scope == "public_corpus"
        assert (
            ensure_external_allowed(session, case_id=case_id, provider="anthropic").id
            == authorization.id
        )

        assert revoke_case(session, case_id=case_id) == 1
        session.commit()
        with pytest.raises(ExternalProcessingBlocked):
            ensure_external_allowed(session, case_id=case_id, provider="anthropic")


def test_new_authorization_revokes_the_previous_one(tmp_path: Path) -> None:
    factory, case_id = _env(tmp_path)

    with factory() as session:
        first = authorize_case(session, case_id=case_id, scope="public_corpus", authorized_by="A")
        session.commit()
        second = authorize_case(session, case_id=case_id, scope="fictional_case", authorized_by="B")
        session.commit()

        assert active_authorization(session, case_id=case_id).id == second.id
        assert session.get(ExternalProcessingAuthorization, first.id).revoked_at
        assert (
            session.scalar(
                select(func.count())
                .select_from(ExternalProcessingAuthorization)
                .where(ExternalProcessingAuthorization.revoked_at.is_(None))
            )
            == 1
        )


def test_invalid_scope_and_identity_are_rejected(tmp_path: Path) -> None:
    factory, case_id = _env(tmp_path)

    with factory() as session:
        with pytest.raises(ValueError):
            authorize_case(session, case_id=case_id, scope="private_case", authorized_by="A")
        with pytest.raises(ValueError):
            authorize_case(session, case_id=case_id, scope="public_corpus", authorized_by=" ")
