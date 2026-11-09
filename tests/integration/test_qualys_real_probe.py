"""Probe local del CSV real filtrado, sin incorporarlo al repositorio."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import Case, QualysVulnerability, QualysVulnerabilityCve
from secguard_advisor.tools.findings import FindingsQuery
from secguard_advisor.vulnerabilities.service import QualysImportService
from secguard_advisor.vulnerabilities.validation import validate_csv

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = ROOT.parent / "14-Qualys_Hallazgos_Active_New_ReOpened.csv"
MANIFEST_PATH = ROOT.parent / "14-Qualys_Hallazgos_Active_New_ReOpened_manifest.json"


def test_real_csv_probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if not CSV_PATH.exists() or not MANIFEST_PATH.exists():
        pytest.skip("El CSV real o su manifiesto no están disponibles localmente.")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    settings = Settings(_env_file=None, storage_dir=tmp_path)

    result = validate_csv(
        CSV_PATH.read_bytes(),
        settings=settings,
        manifest_path=MANIFEST_PATH,
    )
    assert result.status == "staged"
    assert result.manifest.status == "matched"
    assert result.row_count == 662
    assert result.valid_rows == 662
    assert result.invalid_rows == 0
    assert result.status_counts == {"Active": 631, "New": 10, "Re-Opened": 21}
    assert result.exploitability_counts == {"positive": 129, "indeterminate": 533}
    assert result.malware_counts == {"positive": 8, "indeterminate": 654}
    assert result.priority_counts == {"both_positive": 8}
    assert result.possible_repeat_groups == 10
    assert result.possible_repeat_rows == 11
    assert sum(1 for row in result.rows if len(row.cves) > 1) == 179

    engine = create_engine_for_url(f"sqlite:///{tmp_path / 'probe.sqlite3'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        case = Case(
            title="Probe local", synthetic_notice="Prueba local con almacenamiento temporal"
        )
        session.add(case)
        session.commit()
        case_id = case.id

    service = QualysImportService(factory, settings)
    staged = service.stage_import(
        case_id,
        CSV_PATH.name,
        CSV_PATH.read_bytes(),
        manifest_path=MANIFEST_PATH,
    )
    assert staged.import_record.status == "staged"
    assert staged.import_record.row_count == 662
    confirmed = service.confirm_import(case_id, staged.import_record.id)
    assert confirmed.import_record.status == "confirmed"
    with factory() as session:
        vulnerabilities = session.scalar(
            select(func.count())
            .select_from(QualysVulnerability)
            .where(QualysVulnerability.import_id == staged.import_record.id)
        )
        cves = session.scalar(
            select(func.count())
            .select_from(QualysVulnerabilityCve)
            .join(
                QualysVulnerability,
                QualysVulnerabilityCve.vulnerability_id == QualysVulnerability.id,
            )
            .where(QualysVulnerability.import_id == staged.import_record.id)
        )
    assert vulnerabilities == 662
    assert cves is not None and cves >= 662
    again = service.stage_import(case_id, CSV_PATH.name, CSV_PATH.read_bytes())
    assert again.idempotent is True
    assert again.import_record.id == staged.import_record.id
    engine.dispose()


def test_real_csv_advanced_filters_and_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not CSV_PATH.exists() or not MANIFEST_PATH.exists():
        pytest.skip("El CSV real o su manifiesto no están disponibles localmente.")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    settings = Settings(_env_file=None, storage_dir=tmp_path)
    engine = create_engine_for_url(f"sqlite:///{tmp_path / 'filters.sqlite3'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        case = Case(title="Filtros reales", synthetic_notice="Prueba local temporal")
        session.add(case)
        session.commit()
        case_id = case.id
    service = QualysImportService(factory, settings)
    staged = service.stage_import(
        case_id,
        CSV_PATH.name,
        CSV_PATH.read_bytes(),
        manifest_path=MANIFEST_PATH,
    )
    service.confirm_import(case_id, staged.import_record.id)
    query = FindingsQuery(factory, CaseScope(case_id=case_id))

    pending = query.execute({"origin": "imported", "status_group": "pending_known"})
    assert pending["total"] == 662
    assert pending["status_counts"] == {"Active": 631, "New": 10, "Re-Opened": 21}
    assert sum(pending["severity_counts"].values()) == 662
    assert set(pending["severity_counts"]) <= {"1", "2", "3", "4", "5"}
    assert pending["exploitability_counts"]["positive"] == 129
    assert pending["malware_counts"]["positive"] == 8
    assert pending["priority_counts"]["both_positive"] == 8

    assert query.execute({"origin": "imported", "status_group": "fixed"})["total"] == 0
    assert query.execute({"origin": "imported", "status_group": "manual_review"})["total"] == 0
    assert query.execute({"origin": "imported", "priority": True})["total"] == 8
    assert query.execute({"origin": "imported", "exploitability": "positive"})["total"] == 129
    assert query.execute({"origin": "imported", "malware": "positive"})["total"] == 8
    assert (
        query.execute(
            {
                "origin": "imported",
                "status_group": "all",
                "priority": True,
                "exploitability": "positive",
                "malware": "positive",
            }
        )["total"]
        == 8
    )

    status_groups = query.execute(
        {"origin": "imported", "status_group": "all", "group_by": "status"}
    )["groups"]
    assert {group["key"]: group["count"] for group in status_groups} == {
        "pending_known": 662,
    }
    priority_groups = query.execute(
        {"origin": "imported", "status_group": "all", "group_by": "priority"}
    )["groups"]
    assert {group["key"]: group["count"] for group in priority_groups} == {
        "not_priority": 654,
        "priority": 8,
    }

    limited = query.execute(
        {"origin": "imported", "status_group": "all", "detail": True, "limit": 1}
    )
    assert limited["total"] == 662
    assert len(limited["items"]) == 1
    assert limited["truncated"] is True
    assert "Results" not in limited

    with factory() as session:
        multi = session.execute(
            select(QualysVulnerabilityCve.cve)
            .join(
                QualysVulnerability,
                QualysVulnerabilityCve.vulnerability_id == QualysVulnerability.id,
            )
            .where(QualysVulnerability.import_id == staged.import_record.id)
            .group_by(QualysVulnerabilityCve.cve)
            .having(func.count() > 1)
            .limit(1)
        ).scalar_one()
        expected = session.scalar(
            select(func.count(func.distinct(QualysVulnerability.id)))
            .select_from(QualysVulnerability)
            .join(
                QualysVulnerabilityCve,
                QualysVulnerabilityCve.vulnerability_id == QualysVulnerability.id,
            )
            .where(
                QualysVulnerability.import_id == staged.import_record.id,
                QualysVulnerabilityCve.cve == multi,
            )
        )
        relations = session.scalar(
            select(func.count())
            .select_from(QualysVulnerabilityCve)
            .join(
                QualysVulnerability,
                QualysVulnerabilityCve.vulnerability_id == QualysVulnerability.id,
            )
            .where(
                QualysVulnerability.import_id == staged.import_record.id,
                QualysVulnerabilityCve.cve == multi,
            )
        )
    shared = query.execute({"origin": "imported", "status_group": "all", "cve": multi})
    assert expected is not None and expected > 1
    assert relations is not None and relations >= expected
    assert shared["total"] == expected
    engine.dispose()
