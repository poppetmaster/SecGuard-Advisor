"""Integración SQLite de importación, confirmación y consulta básica."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import Case, QualysVulnerability
from secguard_advisor.tools.findings import FindingsQuery
from secguard_advisor.vulnerabilities.service import QualysImportService

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


def test_import_confirm_query_and_reimport(tmp_path: Path) -> None:
    engine = create_engine_for_url(f"sqlite:///{tmp_path / 'import.sqlite3'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        case = Case(title="Caso SQLite", synthetic_notice="Escenario educativo sintético")
        session.add(case)
        session.commit()
        case_id = case.id
    settings = Settings(_env_file=None, storage_dir=tmp_path)
    service = QualysImportService(factory, settings)
    content = (FIXTURES / "qualys_synthetic_valid.csv").read_bytes()

    staged = service.stage_import(
        case_id,
        "valid.csv",
        content,
        manifest_path=FIXTURES / "qualys_synthetic_manifest.json",
    )
    assert staged.import_record.status == "staged"
    confirmed = service.confirm_import(case_id, staged.import_record.id)
    assert confirmed.import_record.status == "confirmed"
    assert confirmed.import_record.confirmed_sequence == 1

    query = FindingsQuery(factory, CaseScope(case_id=case_id))
    result = query.execute({"origin": "imported", "detail": True})
    assert result["total"] == 3
    assert result["snapshot"]["sequence"] == 1
    assert len(result["items"]) == 3

    again = service.stage_import(case_id, "valid.csv", content)
    assert again.idempotent is True
    assert again.import_record.id == staged.import_record.id
    with factory() as session:
        rows = session.scalar(
            select(func.count())
            .select_from(QualysVulnerability)
            .where(QualysVulnerability.import_id == staged.import_record.id)
        )
    assert rows == 5

    rejected = service.stage_import(
        case_id,
        "invalid.csv",
        (FIXTURES / "qualys_synthetic_invalid_rows.csv").read_bytes(),
    )
    assert rejected.import_record.status == "rejected"
    assert service.list_rows(case_id, rejected.import_record.id) == []
    rejected_result = query.execute({"origin": "imported"})
    assert rejected_result["total"] == 3
    assert rejected_result["snapshot"]["id"] == staged.import_record.id
    engine.dispose()
