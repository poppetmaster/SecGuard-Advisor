"""Pruebas de la unidad de trabajo y del control de transacciones."""

from pathlib import Path

import pytest
from sqlalchemy import text

from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import Case
from secguard_advisor.db.transaction import (
    ActiveTransactionError,
    ensure_no_active_transaction,
    unit_of_work,
)


@pytest.fixture
def factory(tmp_path: Path):
    engine = create_engine_for_url(f"sqlite:///{tmp_path / 'tx.sqlite3'}")
    Base.metadata.create_all(engine)
    yield create_session_factory(engine)
    engine.dispose()


def _case() -> Case:
    return Case(title="Caso", synthetic_notice="Escenario educativo sintético")


def test_unit_of_work_commits_and_closes(factory) -> None:
    with unit_of_work(factory) as session:
        session.add(_case())
        captured = session

    assert captured.in_transaction() is False
    with factory() as session:
        assert session.query(Case).count() == 1


def test_unit_of_work_rolls_back_on_error(factory) -> None:
    with pytest.raises(RuntimeError), unit_of_work(factory) as session:
        session.add(_case())
        raise RuntimeError("fallo")

    with factory() as session:
        assert session.query(Case).count() == 0


def test_active_transaction_is_detected(factory) -> None:
    with factory() as session:
        ensure_no_active_transaction(session)
        session.execute(text("SELECT 1"))
        with pytest.raises(ActiveTransactionError):
            ensure_no_active_transaction(session)
        session.rollback()
        ensure_no_active_transaction(session)
