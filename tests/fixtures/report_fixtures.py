"""Fictional datasets for the executive report tests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import (
    Case,
    QualysImport,
    QualysVulnerability,
    QualysVulnerabilityCve,
)
from secguard_advisor.reports.privacy import SEVERITY_LABELS


@dataclass(frozen=True, slots=True)
class ReportContext:
    settings: Settings
    session_factory: sessionmaker[Session]
    case_id: str
    snapshot_id: str


def default_rows() -> list[dict[str, Any]]:
    """Rows with severities, statuses, indicators and a multi-CVE record."""
    return [
        {
            "asset": "host-01.example",
            "severity": 5,
            "status": "pending_known",
            "exploitability": "positive",
            "malware": "positive",
            "qid": "900001",
            "title": "Critical both positive",
            "cves": ["CVE-2026-0001", "CVE-2026-0002"],
        },
        {
            "asset": "host-01.example",
            "severity": 4,
            "status": "pending_known",
            "exploitability": "positive",
            "malware": "negative_no_info",
            "qid": "900002",
            "title": "High exploitability",
        },
        {
            "asset": "host-02.example",
            "severity": 4,
            "status": "pending_known",
            "exploitability": "indeterminate",
            "malware": "indeterminate",
            "qid": "900003",
            "title": "High indeterminate",
        },
        {
            "asset": "host-02.example",
            "severity": 3,
            "status": "pending_known",
            "exploitability": "negative_no_info",
            "malware": "negative_no_info",
            "qid": "900004",
            "title": "Medium clean",
        },
        {
            "asset": "Sin activo",
            "severity": 2,
            "status": "pending_known",
            "exploitability": "indeterminate",
            "malware": "negative_no_info",
            "qid": "900005",
            "title": "Unknown asset",
        },
        {
            "asset": "host-03.example",
            "severity": 5,
            "status": "fixed",
            "exploitability": "positive",
            "malware": "positive",
            "qid": "900006",
            "title": "Fixed antecedent",
        },
        {
            "asset": "host-03.example",
            "severity": 1,
            "status": "manual_review",
            "exploitability": "indeterminate",
            "malware": "indeterminate",
            "qid": "900007",
            "title": "Manual review",
        },
        {
            "asset": "host-04.example",
            "severity": 4,
            "status": "pending_known",
            "exploitability": "positive",
            "malware": "positive",
            "qid": "900008",
            "title": "High both positive",
        },
        {
            "asset": "host-04.example",
            "severity": 5,
            "status": "pending_known",
            "exploitability": "positive",
            "malware": "negative_no_info",
            "qid": "900009",
            "title": "Critical exploitability",
        },
        {
            "asset": "host-05.example",
            "severity": 4,
            "status": "pending_known",
            "exploitability": "negative_no_info",
            "malware": "negative_no_info",
            "qid": "900010",
            "title": "High clean",
        },
    ]


def build_report_context(tmp_path: Path, rows: list[dict[str, Any]] | None = None) -> ReportContext:
    settings = Settings(_env_file=None, storage_dir=tmp_path / "storage")
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    data = rows or default_rows()
    with factory() as session:
        case = Case(title="Caso ficticio 006", synthetic_notice="Escenario educativo sintético")
        session.add(case)
        session.flush()
        snapshot = _snapshot(session, case.id, data)
        session.commit()
        return ReportContext(settings, factory, case.id, snapshot.id)


def _snapshot(session: Session, case_id: str, rows: list[dict[str, Any]]) -> QualysImport:
    status_counts: dict[str, int] = {}
    severity_counts: dict[str, int] = {}
    exploitability_counts: dict[str, int] = {}
    malware_counts: dict[str, int] = {}
    manual_review = 0
    for row in rows:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
        severity_counts[str(row["severity"])] = severity_counts.get(str(row["severity"]), 0) + 1
        exploitability_counts[row["exploitability"]] = (
            exploitability_counts.get(row["exploitability"], 0) + 1
        )
        malware_counts[row["malware"]] = malware_counts.get(row["malware"], 0) + 1
        if (
            row["status"] == "manual_review"
            or row["exploitability"] == "indeterminate"
            or row["malware"] == "indeterminate"
        ):
            manual_review += 1
    snapshot = QualysImport(
        case_id=case_id,
        status="confirmed",
        original_filename="fictional_006.csv",
        csv_sha256="a" * 64,
        csv_bytes=1234,
        manifest_sha256="b" * 64,
        manifest_status="matched",
        row_count=len(rows),
        valid_rows=len(rows),
        invalid_rows=0,
        warning_rows=0,
        manual_review_rows=manual_review,
        possible_repeat_groups=0,
        possible_repeat_rows=0,
        status_counts_json=json.dumps(status_counts),
        severity_counts_json=json.dumps(severity_counts),
        exploitability_counts_json=json.dumps(exploitability_counts),
        malware_counts_json=json.dumps(malware_counts),
        priority_counts_json=json.dumps(
            {
                "both_positive": sum(
                    1
                    for row in rows
                    if row["exploitability"] == "positive" and row["malware"] == "positive"
                )
            }
        ),
        summary_json="{}",
        adapter_version="fictional-006",
        severity_policy_version="severity-v1",
        status_policy_version="status-v1",
        priority_rule_version="priority-v1",
        confirmed_sequence=1,
        confirmed_at="2026-11-23T10:00:00+00:00",
    )
    session.add(snapshot)
    session.flush()
    for index, row in enumerate(rows, start=1):
        status = row["status"]
        vulnerability = QualysVulnerability(
            import_id=snapshot.id,
            case_id=case_id,
            row_number=index,
            raw_json="{}",
            asset_label=row["asset"],
            qid=row["qid"],
            title=row["title"],
            status_raw=status,
            status_normalized=(
                "manual_review"
                if status == "manual_review"
                else "fixed"
                if status == "fixed"
                else "active"
            ),
            status_group=status,
            severity_raw=str(row["severity"]),
            severity_level=row["severity"],
            severity_label=SEVERITY_LABELS[row["severity"]],
            severity_policy_version="severity-v1",
            exploitability_eval=row["exploitability"],
            malware_eval=row["malware"],
            priority_flag=(row["exploitability"] == "positive" and row["malware"] == "positive"),
            priority_rule_version="priority-v1",
        )
        session.add(vulnerability)
        session.flush()
        for cve in row.get("cves", []):
            session.add(QualysVulnerabilityCve(vulnerability_id=vulnerability.id, cve=cve))
    return snapshot
