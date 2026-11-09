"""Contrato externo de findings_query con registros importados."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import select
from tests.fixtures.findings import seed_findings

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import Case, QualysImport
from secguard_advisor.tools.findings import FindingsArguments, FindingsQuery, ToolArgumentError
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


def test_advanced_filters_groups_and_errors(tmp_path: Path) -> None:
    engine = create_engine_for_url(f"sqlite:///{tmp_path / 'advanced.sqlite3'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        case = Case(title="Contrato avanzado", synthetic_notice="Escenario educativo sintético")
        session.add(case)
        session.commit()
        case_id = case.id
    service = QualysImportService(factory, Settings(_env_file=None, storage_dir=tmp_path))
    staged = service.stage_import(
        case_id,
        "valid.csv",
        (FIXTURES / "qualys_synthetic_valid.csv").read_bytes(),
    )
    service.confirm_import(case_id, staged.import_record.id)
    query = FindingsQuery(factory, CaseScope(case_id=case_id))

    assert query.execute({"origin": "imported", "status_group": "fixed"})["total"] == 1
    assert query.execute({"origin": "imported", "status_group": "manual_review"})["total"] == 1
    assert query.execute({"origin": "imported", "status_group": "all"})["total"] == 5
    assert query.execute({"origin": "imported", "severity_level": 5})["total"] == 1
    assert query.execute({"origin": "imported", "priority": True})["total"] == 2
    assert query.execute({"origin": "imported", "exploitability": "positive"})["total"] == 3
    assert query.execute({"origin": "imported", "malware": "positive"})["total"] == 2
    assert (
        query.execute({"origin": "imported", "status_group": "all", "malware": "negative_no_info"})[
            "total"
        ]
        == 1
    )
    assert (
        query.execute(
            {
                "origin": "imported",
                "status_group": "fixed",
                "severity_level": 2,
            }
        )["total"]
        == 1
    )

    status_groups = query.execute(
        {"origin": "imported", "status_group": "all", "group_by": "status"}
    )["groups"]
    assert {group["key"]: group["count"] for group in status_groups} == {
        "fixed": 1,
        "manual_review": 1,
        "pending_known": 3,
    }
    priority_groups = query.execute(
        {"origin": "imported", "status_group": "all", "group_by": "priority"}
    )["groups"]
    assert {group["key"]: group["count"] for group in priority_groups} == {
        "not_priority": 3,
        "priority": 2,
    }
    severity_groups = query.execute(
        {"origin": "imported", "status_group": "all", "group_by": "severity_level"}
    )["groups"]
    assert {group["key"]: group["count"] for group in severity_groups} == {
        "1": 1,
        "2": 1,
        "3": 1,
        "4": 1,
        "5": 1,
    }

    with pytest.raises(ToolArgumentError) as imported_severity:
        query.execute({"origin": "imported", "severity": "High"})
    assert imported_severity.value.code == "filter_not_applicable"

    seed_findings(
        factory,
        case_id=case_id,
        findings=[
            ("synthetic-asset", "High", "900001", []),
            ("synthetic-asset", "Low", "900002", []),
        ],
    )
    mixed = query.execute({"origin": "all", "status_group": "all"})
    assert mixed["origin"] == "all"
    assert {block["origin"]: block["total"] for block in mixed["origins"]} == {
        "synthetic": 2,
        "imported": 5,
    }
    origin_groups = query.execute({"origin": "all", "group_by": "origin"})["groups"]
    assert {group["key"]: group["count"] for group in origin_groups} == {
        "synthetic": 2,
        "imported": 5,
    }

    with pytest.raises(ToolArgumentError) as status_origin:
        query.execute({"origin": "all", "status_group": "fixed"})
    assert status_origin.value.code == "origin_required_for_status_filter"
    with pytest.raises(ToolArgumentError) as priority_origin:
        query.execute({"origin": "all", "priority": True})
    assert priority_origin.value.code == "filter_not_applicable"
    with pytest.raises(ToolArgumentError) as severity_ambiguous:
        query.execute({"origin": "all", "severity": "High"})
    assert severity_ambiguous.value.code == "ambiguous_severity_filter"
    with pytest.raises(ToolArgumentError) as level_ambiguous:
        query.execute({"origin": "all", "severity_level": 3})
    assert level_ambiguous.value.code == "ambiguous_severity_filter"
    with pytest.raises(ToolArgumentError) as synthetic_status:
        query.execute({"origin": "synthetic", "status_group": "all"})
    assert synthetic_status.value.code == "filter_not_applicable"
    with pytest.raises(ToolArgumentError) as synthetic_priority:
        query.execute({"origin": "synthetic", "priority": True})
    assert synthetic_priority.value.code == "filter_not_applicable"
    with pytest.raises(ToolArgumentError) as synthetic_level:
        query.execute({"origin": "synthetic", "severity_level": 3})
    assert synthetic_level.value.code == "filter_not_applicable"
    with pytest.raises(ToolArgumentError) as synthetic_group:
        query.execute({"origin": "synthetic", "group_by": "status"})
    assert synthetic_group.value.code == "filter_not_applicable"
    with pytest.raises(ToolArgumentError) as snapshot_origin:
        query.execute({"origin": "all", "snapshot_id": "a" * 32})
    assert snapshot_origin.value.code == "filter_not_applicable"
    engine.dispose()
