"""Integración de orígenes sintéticos e importados y presupuesto."""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.fixtures.fakes import FakeTokenCounter
from tests.fixtures.findings import seed_findings

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.conversation.budget import plan_prompt
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import Case
from secguard_advisor.tools.findings import FindingsQuery, ToolArgumentError
from secguard_advisor.vulnerabilities.service import QualysImportService

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


def test_mixed_origins_filters_isolation_and_budget(tmp_path: Path) -> None:
    engine = create_engine_for_url(f"sqlite:///{tmp_path / 'origins.sqlite3'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        case = Case(title="Caso orígenes", synthetic_notice="Escenario educativo sintético")
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
    seed_findings(
        factory,
        case_id=case_id,
        findings=[
            ("synthetic-asset", "High", "900001", []),
            ("synthetic-asset", "Low", "900002", []),
        ],
    )
    query = FindingsQuery(factory, CaseScope(case_id=case_id))

    mixed = query.execute({"origin": "all", "status_group": "all"})
    assert mixed["origin"] == "all"
    assert {block["origin"]: block["total"] for block in mixed["origins"]} == {
        "synthetic": 2,
        "imported": 5,
    }
    assert mixed["total"] == 7
    assert query.execute({"origin": "all", "group_by": "origin"})["groups"] == [
        {"key": "synthetic", "count": 2},
        {"key": "imported", "count": 5},
    ]

    with pytest.raises(ToolArgumentError) as ambiguous:
        query.execute({"origin": "all", "severity": "High"})
    assert ambiguous.value.code == "ambiguous_severity_filter"
    with pytest.raises(ToolArgumentError) as status_filter:
        query.execute({"origin": "all", "status_group": "fixed"})
    assert status_filter.value.code == "origin_required_for_status_filter"

    cve = query.execute({"origin": "imported", "cve": "CVE-2024-12345", "detail": True})
    assert cve["total"] == 1
    assert len(cve["items"]) == 1

    plan = plan_prompt(
        question="¿Cuántos registros hay por origen?",
        hits=(),
        history=(),
        settings=Settings(_env_file=None),
        counter=FakeTokenCounter(),
        tool_results=({"tool": "findings_query", "status": "ok", "result": mixed},),
    )
    assert "origins" in plan.user
    assert "Results" not in plan.user
    assert plan.admitted_tokens <= plan.prompt_limit

    with factory() as session:
        other = Case(title="Otro caso", synthetic_notice="Escenario educativo sintético")
        session.add(other)
        session.commit()
        other_id = other.id
    with pytest.raises(ToolArgumentError) as foreign:
        FindingsQuery(factory, CaseScope(case_id=other_id)).execute(
            {"origin": "imported", "snapshot_id": staged.import_record.id}
        )
    assert foreign.value.code == "snapshot_not_found"
    engine.dispose()
