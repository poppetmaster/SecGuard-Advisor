"""Integración de snapshots históricos Qualys sobre SQLite."""

from __future__ import annotations

from pathlib import Path

import pytest

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import Case
from secguard_advisor.tools.findings import FindingsQuery
from secguard_advisor.vulnerabilities.service import QualysImportService

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


def test_two_snapshots_are_independent_and_idempotent(tmp_path: Path) -> None:
    engine = create_engine_for_url(f"sqlite:///{tmp_path / 'snapshots.sqlite3'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        case = Case(title="Caso snapshots", synthetic_notice="Escenario educativo sintético")
        session.add(case)
        session.commit()
        case_id = case.id
    service = QualysImportService(factory, Settings(_env_file=None, storage_dir=tmp_path))
    first = service.stage_import(
        case_id,
        "first.csv",
        (FIXTURES / "qualys_synthetic_valid.csv").read_bytes(),
    )
    service.confirm_import(case_id, first.import_record.id)
    second = service.stage_import(
        case_id,
        "second.csv",
        (FIXTURES / "qualys_synthetic_second.csv").read_bytes(),
    )
    service.confirm_import(case_id, second.import_record.id)

    query = FindingsQuery(factory, CaseScope(case_id=case_id))
    latest = query.execute({"origin": "imported"})
    previous = query.execute({"origin": "imported", "snapshot_id": first.import_record.id})
    assert latest["snapshot"]["sequence"] == 2
    assert latest["total"] == 2
    assert previous["snapshot"]["sequence"] == 1
    assert previous["total"] == 3
    assert latest["total"] + previous["total"] == 5

    repeated = service.stage_import(
        case_id,
        "first.csv",
        (FIXTURES / "qualys_synthetic_valid.csv").read_bytes(),
    )
    assert repeated.idempotent is True
    assert len(service.list_confirmed(case_id)) == 2
    assert query.execute({"origin": "imported"})["total"] == 2
    assert (
        query.execute({"origin": "imported", "snapshot_id": first.import_record.id})["total"] == 3
    )
    engine.dispose()
