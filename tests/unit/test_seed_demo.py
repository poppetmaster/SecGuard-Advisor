"""Pruebas del dataset sintético determinista."""

from pathlib import Path

import pytest
from sqlalchemy import func, select

from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import (
    Asset,
    Case,
    Finding,
    SyntheticDataset,
)
from secguard_advisor.seed.demo import (
    DEMO_PROVENANCE,
    SeedConflictError,
    build_demo_dataset,
    seed_demo,
)


@pytest.fixture
def session(tmp_path: Path):
    engine = create_engine_for_url(f"sqlite:///{tmp_path / 'seed.sqlite3'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as db_session:
        yield db_session
    engine.dispose()


def test_dataset_is_deterministic() -> None:
    first = build_demo_dataset()
    second = build_demo_dataset()

    assert first.checksum == second.checksum
    assert first.checksum
    assert len(first.findings) == 12


def test_different_seed_changes_checksum() -> None:
    assert build_demo_dataset(1).checksum != build_demo_dataset(2).checksum


def test_seed_is_idempotent_and_scoped_to_the_demo_case(session) -> None:
    first = seed_demo(session)
    second = seed_demo(session)

    assert first.created is True
    assert second.created is False
    assert first.checksum == second.checksum
    assert second.assets == 3
    assert second.findings == 12

    assert session.scalar(select(func.count()).select_from(Case)) == 1
    assert session.scalar(select(func.count()).select_from(Asset)) == 3
    assert session.scalar(select(func.count()).select_from(Finding)) == 12

    dataset = session.scalar(
        select(SyntheticDataset).where(SyntheticDataset.name == "demo-findings")
    )
    assert dataset is not None
    assert dataset.applies_to_case_id == first.case_id
    assert dataset.checksum == first.checksum

    findings = session.scalars(select(Finding)).all()
    assert all(finding.is_synthetic for finding in findings)
    assert all(finding.provenance == DEMO_PROVENANCE for finding in findings)


def test_conflicting_dataset_is_rejected(session) -> None:
    seed_demo(session)
    dataset = session.scalar(
        select(SyntheticDataset).where(SyntheticDataset.name == "demo-findings")
    )
    dataset.checksum = "0" * 64
    session.commit()

    with pytest.raises(SeedConflictError):
        seed_demo(session)
