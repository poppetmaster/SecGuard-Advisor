"""Pruebas de findings_query: argumentos, filtros, conteos y aislamiento."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import func, select
from tests.fixtures.findings import seed_empty_case, seed_findings

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import Asset, Finding, FindingCve
from secguard_advisor.tools.findings import (
    FindingsArguments,
    FindingsQuery,
    ToolArgumentError,
    ToolTimeout,
)

FINDINGS = [
    ("api-gateway", "Critical", "900001", ["CVE-2024-0001", "CVE-2024-0002"]),
    ("api-gateway", "High", "900002", []),
    ("api-gateway", "Medium", "900003", ["CVE-2024-0003"]),
    ("customer-portal", "High", "900004", ["CVE-2024-0004"]),
    ("customer-portal", "Low", "900005", []),
    ("internal-wiki", "High", "900006", []),
    ("internal-wiki", "Info", "900007", []),
]


@pytest.fixture
def context(tmp_path: Path):
    engine = create_engine_for_url(f"sqlite:///{tmp_path / 'findings.sqlite3'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    seeded = seed_findings(factory, findings=FINDINGS)
    yield factory, seeded
    engine.dispose()


def _query(factory, case_id: str, timeout: float = 5.0) -> FindingsQuery:
    return FindingsQuery(factory, CaseScope(case_id=case_id), timeout_seconds=timeout)


def test_without_filters_returns_total_groups_and_dataset(context) -> None:
    factory, seeded = context

    result = _query(factory, seeded.case_id).execute({})

    assert result["total"] == len(FINDINGS)
    assert {group["key"]: group["count"] for group in result["groups"]} == {
        "Critical": 1,
        "High": 3,
        "Medium": 1,
        "Low": 1,
        "Info": 1,
    }
    assert "items" not in result
    assert result["truncated"] is False
    assert result["dataset"] == {
        "name": seeded.dataset_name,
        "version": seeded.dataset_version,
        "checksum": seeded.dataset_checksum,
        "is_synthetic": True,
    }
    assert "case_id" not in json.dumps(result)
    assert seeded.case_id not in json.dumps(result)


def test_individual_and_combined_filters(context) -> None:
    factory, seeded = context
    query = _query(factory, seeded.case_id)

    by_asset = query.execute({"asset": "api-gateway"})
    by_severity = query.execute({"severity": "High"})
    by_qid = query.execute({"qid": "900004"})
    by_cve = query.execute({"cve": "CVE-2024-0003"})
    combined = query.execute({"asset": "api-gateway", "severity": "High"})

    assert by_asset["total"] == 3
    assert by_severity["total"] == 3
    assert by_qid["total"] == 1
    assert by_cve["total"] == 1
    assert combined["total"] == 1


def test_cve_filter_does_not_multiply_findings(context) -> None:
    factory, seeded = context
    query = _query(factory, seeded.case_id)

    result = query.execute({"cve": "CVE-2024-0001", "detail": True, "limit": 10})

    assert result["total"] == 1
    assert len(result["items"]) == 1
    assert result["items"][0]["cves"] == ["CVE-2024-0001", "CVE-2024-0002"]


def test_counts_match_independent_recalculation(context) -> None:
    factory, seeded = context
    query = _query(factory, seeded.case_id)

    result = query.execute({"asset": "api-gateway"})
    with factory() as session:
        asset = session.scalar(
            select(Asset).where(Asset.name == "api-gateway", Asset.case_id == seeded.case_id)
        )
        expected = session.scalar(
            select(func.count())
            .select_from(Finding)
            .where(Finding.case_id == seeded.case_id, Finding.asset_id == asset.id)
        )
        expected_high = session.scalar(
            select(func.count())
            .select_from(Finding)
            .where(
                Finding.case_id == seeded.case_id,
                Finding.asset_id == asset.id,
                Finding.severity_label == "High",
            )
        )

    assert result["total"] == expected
    groups = {group["key"]: group["count"] for group in result["groups"]}
    assert groups["High"] == expected_high


def test_group_by_asset_and_severity(context) -> None:
    factory, seeded = context
    query = _query(factory, seeded.case_id)

    by_asset = query.execute({"group_by": "asset"})
    by_severity = query.execute({"group_by": "severity"})

    assert {group["key"] for group in by_asset["groups"]} == {
        "api-gateway",
        "customer-portal",
        "internal-wiki",
    }
    assert {group["key"] for group in by_severity["groups"]} == {
        "Critical",
        "High",
        "Medium",
        "Low",
        "Info",
    }
    assert sum(group["count"] for group in by_asset["groups"]) == len(FINDINGS)


def test_detail_limit_and_truncated(context) -> None:
    factory, seeded = context
    query = _query(factory, seeded.case_id)

    limited = query.execute({"detail": True, "limit": 2})
    complete = query.execute({"detail": True, "limit": 100})

    assert len(limited["items"]) == 2
    assert limited["truncated"] is True
    assert limited["total"] == len(FINDINGS)
    assert len(complete["items"]) == len(FINDINGS)
    assert complete["truncated"] is False
    item = complete["items"][0]
    assert item["severity_label"] == "Critical"
    assert item["cvss_base"] == 7.5
    assert item["provenance"] == "synthetic:demo-findings-v1"
    assert item["first_detected"] == "2026-01-10"


def test_missing_values_are_not_invented(context) -> None:
    factory, seeded = context
    result = _query(factory, seeded.case_id).execute(
        {"severity": "Info", "detail": True, "limit": 5}
    )

    assert result["items"][0]["cvss_base"] is None
    assert result["items"][0]["cves"] == []


def test_limit_does_not_affect_counts(context) -> None:
    factory, seeded = context
    query = _query(factory, seeded.case_id)

    small = query.execute({"detail": True, "limit": 1})
    large = query.execute({"detail": True, "limit": 100})

    assert small["total"] == large["total"]
    assert small["groups"] == large["groups"]


@pytest.mark.parametrize(
    ("arguments", "code"),
    [
        ({"severity": "Baja"}, "invalid_severity"),
        ({"qid": "abc"}, "invalid_qid"),
        ({"cve": "2024-0001"}, "invalid_cve"),
        ({"limit": 0}, "limit_out_of_range"),
        ({"limit": 101}, "limit_out_of_range"),
        ({"detail": "sí"}, "invalid_arguments"),
        ({"case_id": "a" * 32}, "invalid_arguments"),
        ({"sql": "select * from findings"}, "invalid_arguments"),
    ],
)
def test_invalid_arguments_are_rejected(context, arguments, code) -> None:
    factory, seeded = context

    with pytest.raises(ToolArgumentError) as captured:
        _query(factory, seeded.case_id).execute(arguments)

    assert captured.value.code == code


def test_empty_case_returns_an_empty_result(context) -> None:
    factory, _seeded = context
    empty_id = seed_empty_case(factory)

    result = _query(factory, empty_id).execute({})

    assert result["total"] == 0
    assert result["groups"] == []
    assert "items" not in result
    assert result["truncated"] is False
    assert result["dataset"]["is_synthetic"] is True


def test_two_cases_are_isolated(context, tmp_path: Path) -> None:
    factory, seeded = context
    other = seed_findings(
        factory,
        title="Otro caso",
        findings=[("activo-exclusivo-b", "Critical", "800001", [])],
    )

    first = _query(factory, seeded.case_id).execute({"asset": "activo-exclusivo-b"})
    second = _query(factory, other.case_id).execute({})

    assert first["total"] == 0
    assert second["total"] == 1
    assert "items" not in second


def test_schema_does_not_expose_case_id_or_free_sql() -> None:
    schema = FindingsArguments.model_json_schema()

    assert "case_id" not in schema["properties"]
    assert schema["additionalProperties"] is False
    assert "sql" not in json.dumps(schema).casefold()
    assert set(schema["properties"]) == {
        "origin",
        "snapshot_id",
        "asset",
        "severity",
        "severity_level",
        "status_group",
        "priority",
        "exploitability",
        "malware",
        "qid",
        "cve",
        "group_by",
        "detail",
        "limit",
    }


def test_timeout_is_reported(context, monkeypatch) -> None:
    factory, seeded = context
    import secguard_advisor.tools.findings as module

    ticks = iter([0.0, 10.0])
    monkeypatch.setattr(module, "perf_counter", lambda: next(ticks))

    with pytest.raises(ToolTimeout):
        _query(factory, seeded.case_id, timeout=1.0).execute({"detail": True})


def test_cves_are_fetched_once_per_finding(context) -> None:
    factory, seeded = context
    result = _query(factory, seeded.case_id).execute({"qid": "900001", "detail": True, "limit": 5})

    with factory() as session:
        expected = session.scalar(
            select(func.count())
            .select_from(FindingCve)
            .where(FindingCve.finding_id == seeded.findings[0].id)
        )
    assert len(result["items"][0]["cves"]) == expected == 2
