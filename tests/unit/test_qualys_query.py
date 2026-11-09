"""Pruebas unitarias de la consulta básica de registros Qualys importados."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import func, select
from tests.fixtures.findings import seed_findings

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import Case, QualysVulnerability
from secguard_advisor.tools.findings import FindingsQuery, ToolArgumentError
from secguard_advisor.vulnerabilities.service import QualysImportService

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


@pytest.fixture
def query_env(tmp_path: Path):
    engine = create_engine_for_url(f"sqlite:///{tmp_path / 'query.sqlite3'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        case = Case(title="Caso consulta", synthetic_notice="Escenario educativo sintético")
        session.add(case)
        session.commit()
        case_id = case.id
    service = QualysImportService(factory, Settings(_env_file=None, storage_dir=tmp_path))
    staged = service.stage_import(
        case_id,
        "qualys_synthetic_valid.csv",
        (FIXTURES / "qualys_synthetic_valid.csv").read_bytes(),
        manifest_path=FIXTURES / "qualys_synthetic_manifest.json",
    )
    confirmed = service.confirm_import(case_id, staged.import_record.id)
    yield factory, case_id, confirmed.import_record.id
    engine.dispose()


def _query(factory, case_id: str) -> FindingsQuery:
    return FindingsQuery(factory, CaseScope(case_id=case_id))


def test_imported_default_snapshot_pending_known_and_detail(query_env) -> None:
    factory, case_id, import_id = query_env
    result = _query(factory, case_id).execute({"origin": "imported", "detail": True})

    assert result["origin"] == "imported"
    assert result["snapshot"]["id"] == import_id
    assert result["snapshot"]["sequence"] == 1
    assert result["status_group"] == "pending_known"
    assert result["total"] == 3
    assert {group["key"]: group["count"] for group in result["groups"]} == {
        "3": 1,
        "4": 1,
        "5": 1,
    }
    assert len(result["items"]) == 3
    assert result["truncated"] is False
    assert result["priority_counts"] == {"both_positive": 2}
    assert "case_id" not in json.dumps(result)
    assert case_id not in json.dumps(result)
    assert "results" not in json.dumps(result).casefold()
    assert result["items"][0]["cves"] is not None


def test_cve_filter_does_not_multiply_imported_rows(query_env) -> None:
    factory, case_id, _import_id = query_env
    result = _query(factory, case_id).execute(
        {"origin": "imported", "cve": "CVE-2024-12345", "detail": True, "limit": 10}
    )

    assert result["total"] == 1
    assert len(result["items"]) == 1
    assert set(result["items"][0]["cves"]) == {"CVE-2024-0001", "CVE-2024-12345"}
    with factory() as session:
        stored = session.scalar(select(func.count()).select_from(QualysVulnerability))
    assert stored == 5


def test_detail_limit_and_truncation(query_env) -> None:
    factory, case_id, _import_id = query_env
    result = _query(factory, case_id).execute({"origin": "imported", "detail": True, "limit": 1})

    assert result["total"] == 3
    assert len(result["items"]) == 1
    assert result["truncated"] is True


def test_unconfirmed_import_is_not_queryable(query_env) -> None:
    factory, _case_id, _import_id = query_env
    with factory() as session:
        other = Case(title="Caso staged", synthetic_notice="Escenario educativo sintético")
        session.add(other)
        session.commit()
        other_id = other.id
    service = QualysImportService(factory, Settings(_env_file=None, storage_dir=Path(".")))
    service.stage_import(
        other_id,
        "staged.csv",
        (FIXTURES / "qualys_synthetic_valid.csv").read_bytes(),
    )
    result = _query(factory, other_id).execute({"origin": "imported"})
    assert result["snapshot"] is None
    assert result["total"] == 0
    assert result["empty_reason"] == "no_confirmed_import"


def test_snapshot_scope_and_not_found(query_env) -> None:
    factory, case_id, import_id = query_env
    current = _query(factory, case_id).execute({"origin": "imported", "snapshot_id": import_id})
    assert current["snapshot"]["id"] == import_id

    with factory() as session:
        other = Case(title="Otro caso", synthetic_notice="Escenario educativo sintético")
        session.add(other)
        session.commit()
        other_id = other.id
    with pytest.raises(ToolArgumentError) as error:
        _query(factory, other_id).execute({"origin": "imported", "snapshot_id": import_id})
    assert error.value.code == "snapshot_not_found"


def test_mixed_origins_and_filter_applicability(query_env) -> None:
    factory, case_id, _import_id = query_env
    seed_findings(
        factory,
        case_id=case_id,
        findings=[
            ("synthetic-asset", "High", "900001", []),
            ("synthetic-asset", "Low", "900002", []),
        ],
    )
    result = _query(factory, case_id).execute({"origin": "all"})
    assert result["origin"] == "all"
    assert [block["origin"] for block in result["origins"]] == ["synthetic", "imported"]
    assert result["total"] == 7
    assert {block["origin"]: block["total"] for block in result["origins"]} == {
        "synthetic": 2,
        "imported": 5,
    }

    with pytest.raises(ToolArgumentError) as ambiguous:
        _query(factory, case_id).execute({"origin": "all", "severity": "High"})
    assert ambiguous.value.code == "ambiguous_severity_filter"

    with pytest.raises(ToolArgumentError) as snapshot_all:
        _query(factory, case_id).execute({"origin": "all", "snapshot_id": "a" * 32})
    assert snapshot_all.value.code == "filter_not_applicable"

    with pytest.raises(ToolArgumentError) as imported_severity:
        _query(factory, case_id).execute({"origin": "imported", "severity": "High"})
    assert imported_severity.value.code == "filter_not_applicable"

    with pytest.raises(ToolArgumentError) as synthetic_snapshot:
        _query(factory, case_id).execute({"origin": "synthetic", "snapshot_id": "a" * 32})
    assert synthetic_snapshot.value.code == "filter_not_applicable"
