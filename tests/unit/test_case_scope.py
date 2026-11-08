"""Pruebas del alcance de caso."""

from pathlib import Path

import pytest

from secguard_advisor.cases.scope import (
    CaseNotFoundError,
    CaseScope,
    require_case,
    resolve_case_scope,
)
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import Case


@pytest.fixture
def session(tmp_path: Path):
    engine = create_engine_for_url(f"sqlite:///{tmp_path / 'scope.sqlite3'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as db_session:
        yield db_session
    engine.dispose()


def _case(session, title: str) -> Case:
    case = Case(title=title, synthetic_notice="Escenario educativo sintético")
    session.add(case)
    session.commit()
    return case


def test_resolves_only_the_requested_case(session) -> None:
    first = _case(session, "Caso A")
    second = _case(session, "Caso B")

    scope = resolve_case_scope(session, second.id)

    assert scope == CaseScope(case_id=second.id)
    assert require_case(session, scope).id == second.id
    assert require_case(session, scope).id != first.id


def test_unknown_case_is_rejected(session) -> None:
    with pytest.raises(CaseNotFoundError):
        resolve_case_scope(session, "0" * 32)


def test_empty_case_is_rejected(session) -> None:
    with pytest.raises(CaseNotFoundError):
        resolve_case_scope(session, "")


def test_scope_is_immutable() -> None:
    scope = CaseScope(case_id="abc")

    with pytest.raises(AttributeError):
        scope.case_id = "otro"  # type: ignore[misc]
