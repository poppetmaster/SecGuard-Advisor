"""Contrato externo de findings_query con registros importados."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import Case, QualysImport
from secguard_advisor.tools.findings import FindingsArguments, FindingsQuery
from secguard_advisor.vulnerabilities.service import QualysImportService

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


def test_imported_result_contract(tmp_path: Path) -> None:
    engine = create_engine_for_url(f"sqlite:///{tmp_path / 'contract.sqlite3'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        case = Case(title="Contrato", synthetic_notice="Escenario educativo sintético")
        session.add(case)
        session.commit()
        case_id = case.id
    service = QualysImportService(factory, Settings(_env_file=None, storage_dir=tmp_path))
    staged = service.stage_import(
        case_id,
        "qualys_synthetic_valid.csv",
        (FIXTURES / "qualys_synthetic_valid.csv").read_bytes(),
    )
    service.confirm_import(case_id, staged.import_record.id)

    result = FindingsQuery(factory, CaseScope(case_id=case_id)).execute(
        {"origin": "imported", "detail": True, "limit": 2}
    )

    assert result["origin"] == "imported"
    assert result["snapshot"]["sequence"] == 1
    assert result["snapshot"]["id"] == staged.import_record.id
    assert result["status_group"] == "pending_known"
    assert result["total"] == 3
    assert result["truncated"] is True
    assert len(result["items"]) == 2
    assert result["items"][0]["import_id"] == staged.import_record.id
    assert "case_id" not in json.dumps(result)
    assert "results" not in json.dumps(result).casefold()
    assert "select " not in json.dumps(result).casefold()

    schema = FindingsArguments.model_json_schema()
    assert "case_id" not in schema["properties"]
    assert schema["additionalProperties"] is False
    assert {"origin", "snapshot_id"} <= set(schema["properties"])
    with factory() as session:
        records = list(session.scalars(select(QualysImport).where(QualysImport.case_id == case_id)))
        assert [record.status for record in records] == ["confirmed"]
    engine.dispose()
