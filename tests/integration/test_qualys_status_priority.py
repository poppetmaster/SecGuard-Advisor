"""Integración de estados, severidad, indicadores y prioridad Qualys."""

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


def _query(tmp_path: Path, fixture: str):
    engine = create_engine_for_url(f"sqlite:///{tmp_path / 'status.sqlite3'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        case = Case(title="Caso estado", synthetic_notice="Escenario educativo sintético")
        session.add(case)
        session.commit()
        case_id = case.id
    service = QualysImportService(factory, Settings(_env_file=None, storage_dir=tmp_path))
    staged = service.stage_import(case_id, fixture, (FIXTURES / fixture).read_bytes())
    service.confirm_import(case_id, staged.import_record.id)
    return factory, FindingsQuery(factory, CaseScope(case_id=case_id)), engine


def test_states_severity_indicators_and_priority(tmp_path: Path) -> None:
    _factory, query, engine = _query(tmp_path, "qualys_synthetic_valid.csv")
    all_rows = query.execute({"origin": "imported", "status_group": "all"})
    assert all_rows["total"] == 5
    assert all_rows["status_counts"] == {
        "Active": 1,
        "New": 1,
        "Re-Opened": 1,
        "Fixed": 1,
        "UnknownState": 1,
    }
    assert all_rows["severity_counts"] == {"1": 1, "2": 1, "3": 1, "4": 1, "5": 1}
    assert all_rows["exploitability_counts"] == {"positive": 3, "indeterminate": 2}
    assert all_rows["malware_counts"] == {
        "positive": 2,
        "negative_no_info": 1,
        "indeterminate": 2,
    }
    assert all_rows["priority_counts"] == {"both_positive": 2}

    assert query.execute({"origin": "imported", "status_group": "pending_known"})["total"] == 3
    assert query.execute({"origin": "imported", "status_group": "fixed"})["total"] == 1
    assert query.execute({"origin": "imported", "status_group": "manual_review"})["total"] == 1
    assert (
        query.execute(
            {"origin": "imported", "status_group": "all", "severity_level": 5, "detail": True}
        )["items"][0]["severity_label"]
        == "Crítica"
    )
    assert (
        query.execute(
            {"origin": "imported", "status_group": "all", "priority": True, "detail": True}
        )["total"]
        == 2
    )
    fixed = query.execute(
        {
            "origin": "imported",
            "status_group": "fixed",
            "exploitability": "indeterminate",
            "malware": "negative_no_info",
            "detail": True,
        }
    )
    assert fixed["total"] == 1
    assert fixed["items"][0]["status"] == "Fixed"
    assert fixed["items"][0]["priority"] is False
    engine.dispose()


def test_fixed_with_both_indicators_is_context_not_remediation(tmp_path: Path) -> None:
    _factory, query, engine = _query(tmp_path, "qualys_synthetic_mixed.csv")
    result = query.execute(
        {
            "origin": "imported",
            "status_group": "fixed",
            "priority": True,
            "detail": True,
        }
    )
    assert result["total"] == 1
    item = result["items"][0]
    assert item["status"] == "Fixed"
    assert item["priority"] is True
    assert item["priority_reason"] == "Explotabilidad positiva y malware positivo"
    engine.dispose()


def test_manual_review_rows_are_unique_union_not_sum(tmp_path: Path) -> None:
    _factory, query, engine = _query(tmp_path, "qualys_synthetic_valid.csv")
    all_rows = query.execute({"origin": "imported", "status_group": "all"})
    assert all_rows["total"] == 5
    assert all_rows["status_counts"] == {
        "Active": 1,
        "New": 1,
        "Re-Opened": 1,
        "Fixed": 1,
        "UnknownState": 1,
    }
    assert all_rows["exploitability_counts"] == {"positive": 3, "indeterminate": 2}
    assert all_rows["malware_counts"] == {
        "positive": 2,
        "negative_no_info": 1,
        "indeterminate": 2,
    }
    # Filas 3, 4 y 5: la unión es 3, no la suma 1 + 2 + 2.
    assert all_rows["manual_review_rows"] == 3
    assert query.execute({"origin": "imported", "status_group": "manual_review"})["total"] == 1
    assert (
        query.execute(
            {
                "origin": "imported",
                "status_group": "all",
                "exploitability": "indeterminate",
            }
        )["total"]
        == 2
    )
    assert (
        query.execute({"origin": "imported", "status_group": "all", "malware": "indeterminate"})[
            "total"
        ]
        == 2
    )
    engine.dispose()
