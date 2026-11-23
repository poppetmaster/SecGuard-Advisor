"""Deterministic SQLite metrics for the executive report."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from secguard_advisor.db.models import QualysImport, QualysVulnerability, QualysVulnerabilityCve
from secguard_advisor.reports.privacy import SEVERITY_LABELS


@dataclass(frozen=True, slots=True)
class ReportFilters:
    asset: str | None = None
    qid: str | None = None
    cve: str | None = None
    severity_level: int | None = None
    exploitability: str | None = None
    malware: str | None = None
    priority: bool | None = None
    status_group: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "asset": self.asset,
            "qid": self.qid,
            "cve": self.cve,
            "severity_level": self.severity_level,
            "exploitability": self.exploitability,
            "malware": self.malware,
            "priority": self.priority,
            "status_group": self.status_group,
        }


def _filters(case_id: str, snapshot: QualysImport, filters: ReportFilters) -> list:
    clauses = [
        QualysVulnerability.case_id == case_id,
        QualysVulnerability.import_id == snapshot.id,
    ]
    if filters.asset:
        clauses.append(QualysVulnerability.asset_label == filters.asset)
    if filters.qid:
        clauses.append(QualysVulnerability.qid == filters.qid)
    if filters.cve:
        clauses.append(
            QualysVulnerability.id.in_(
                select(QualysVulnerabilityCve.vulnerability_id).where(
                    QualysVulnerabilityCve.cve == filters.cve
                )
            )
        )
    if filters.severity_level is not None:
        clauses.append(QualysVulnerability.severity_level == filters.severity_level)
    if filters.exploitability:
        clauses.append(QualysVulnerability.exploitability_eval == filters.exploitability)
    if filters.malware:
        clauses.append(QualysVulnerability.malware_eval == filters.malware)
    if filters.priority is not None:
        clauses.append(QualysVulnerability.priority_flag == filters.priority)
    if filters.status_group:
        clauses.append(QualysVulnerability.status_group == filters.status_group)
    return clauses


def _count(session: Session, clauses: list) -> int:
    statement = select(func.count()).select_from(QualysVulnerability).where(*clauses)
    return int(session.scalar(statement) or 0)


def _indicator_counts(session: Session, clauses: list) -> dict[str, int]:
    rows = session.execute(
        select(
            QualysVulnerability.exploitability_eval,
            func.count(),
        )
        .where(*clauses)
        .group_by(QualysVulnerability.exploitability_eval)
    ).all()
    counts = {"positive": 0, "negative_no_info": 0, "indeterminate": 0}
    for key, value in rows:
        counts[key] = int(value)
    return counts


def _malware_counts(session: Session, clauses: list) -> dict[str, int]:
    rows = session.execute(
        select(QualysVulnerability.malware_eval, func.count())
        .where(*clauses)
        .group_by(QualysVulnerability.malware_eval)
    ).all()
    counts = {"positive": 0, "negative_no_info": 0, "indeterminate": 0}
    for key, value in rows:
        counts[key] = int(value)
    return counts


def build_metrics(
    session: Session,
    *,
    case_id: str,
    snapshot: QualysImport,
    filters: ReportFilters | None = None,
) -> dict[str, Any]:
    """Build the deterministic metric block consumed by cards and charts."""
    active = filters or ReportFilters()
    clauses = _filters(case_id, snapshot, active)

    def _with(*extra) -> list:
        return [*clauses, *extra]

    total = _count(session, clauses)
    pending = _count(session, _with(QualysVulnerability.status_group == "pending_known"))
    fixed = _count(session, _with(QualysVulnerability.status_group == "fixed"))
    manual_review = _count(
        session,
        _with(
            or_(
                QualysVulnerability.status_group == "manual_review",
                QualysVulnerability.exploitability_eval == "indeterminate",
                QualysVulnerability.malware_eval == "indeterminate",
            )
        ),
    )
    unknown_asset_rows = _count(
        session,
        _with(
            QualysVulnerability.status_group == "pending_known",
            QualysVulnerability.asset_label == "Sin activo",
        ),
    )

    severity_rows = session.execute(
        select(
            QualysVulnerability.severity_level,
            QualysVulnerability.status_group,
            func.count(),
        )
        .where(*clauses)
        .group_by(QualysVulnerability.severity_level, QualysVulnerability.status_group)
    ).all()
    severity = {
        level: {"level": level, "label": SEVERITY_LABELS[level], "pending": 0, "fixed": 0}
        for level in range(1, 6)
    }
    for level, group, count in severity_rows:
        if group == "pending_known":
            severity[level]["pending"] = int(count)
        elif group == "fixed":
            severity[level]["fixed"] = int(count)

    asset_rows = session.execute(
        select(
            QualysVulnerability.asset_label,
            func.sum(case((QualysVulnerability.severity_level == 5, 1), else_=0)),
            func.sum(case((QualysVulnerability.severity_level == 4, 1), else_=0)),
            func.count(),
        )
        .where(
            *clauses,
            QualysVulnerability.status_group == "pending_known",
            QualysVulnerability.severity_level.in_((4, 5)),
            QualysVulnerability.asset_label != "Sin activo",
        )
        .group_by(QualysVulnerability.asset_label)
    ).all()
    assets = [
        {
            "asset_label": label,
            "critical": int(critical or 0),
            "high": int(high or 0),
            "total": int(total_rows or 0),
        }
        for label, critical, high, total_rows in asset_rows
    ]
    assets.sort(
        key=lambda item: (
            -item["critical"],
            -item["high"],
            -item["total"],
            item["asset_label"].lower(),
        )
    )
    distinct_assets = int(
        session.scalar(
            select(func.count(func.distinct(QualysVulnerability.asset_label))).where(
                *clauses,
                QualysVulnerability.status_group == "pending_known",
                QualysVulnerability.asset_label != "Sin activo",
            )
        )
        or 0
    )
    records_critical_high = sum(item["total"] for item in assets)
    assets_with_critical_high = len(assets)

    pending_clauses = _with(QualysVulnerability.status_group == "pending_known")
    exploitability = _indicator_counts(session, pending_clauses)
    malware = _malware_counts(session, pending_clauses)
    both_positive = _count(
        session,
        _with(
            QualysVulnerability.status_group == "pending_known",
            QualysVulnerability.exploitability_eval == "positive",
            QualysVulnerability.malware_eval == "positive",
        ),
    )
    critical_pending = _count(
        session,
        _with(
            QualysVulnerability.status_group == "pending_known",
            QualysVulnerability.severity_level == 5,
        ),
    )
    high_pending = _count(
        session,
        _with(
            QualysVulnerability.status_group == "pending_known",
            QualysVulnerability.severity_level == 4,
        ),
    )
    exploitability_positive = exploitability["positive"]
    malware_positive = malware["positive"]

    def ratio(value: int, denominator: int) -> float:
        return round(value / denominator, 4) if denominator else 0.0

    return {
        "base": {
            "total_rows": total,
            "pending_known": pending,
            "fixed": fixed,
            "manual_review": manual_review,
            "unknown_asset_rows": unknown_asset_rows,
        },
        "cards": {
            "pending": {
                "value": pending,
                "scope": "pending_known",
                "denominator": total,
                "definition": "Active, New y Re-Opened",
            },
            "critical_pending": {
                "value": critical_pending,
                "scope": "pending_known & severity_level=5",
                "denominator": pending,
            },
            "high_pending": {
                "value": high_pending,
                "scope": "pending_known & severity_level=4",
                "denominator": pending,
            },
            "distinct_assets_pending": {
                "value": distinct_assets,
                "scope": "pending_known",
                "denominator": pending,
                "identifier": "FQDN > DNS > NetBIOS > IP",
                "unknown_asset_rows": unknown_asset_rows,
            },
            "exploitability_positive_pending": {
                "value": exploitability_positive,
                "scope": "pending_known & exploitability_eval=positive",
                "denominator": pending,
            },
            "malware_positive_pending": {
                "value": malware_positive,
                "scope": "pending_known & malware_eval=positive",
                "denominator": pending,
            },
            "both_positive_pending": {
                "value": both_positive,
                "scope": "pending_known & ambos positivos",
                "denominator": pending,
            },
            "fixed": {"value": fixed, "scope": "fixed", "denominator": total},
            "manual_review": {
                "value": manual_review,
                "scope": "estado desconocido o explotabilidad o malware indeterminados",
                "denominator": total,
            },
        },
        "severity": {
            "levels": [severity[level] for level in range(1, 6)],
            "denominator_pending": pending,
            "denominator_fixed": fixed,
        },
        "assets_top": {
            "top_n": 5,
            "total_assets": distinct_assets,
            "assets_with_critical_or_high": assets_with_critical_high,
            "records_critical_or_high": records_critical_high,
            "recorted": len(assets) > 5,
            "items": assets[:5],
            "others": {
                "assets": max(0, assets_with_critical_high - 5),
                "records": sum(item["total"] for item in assets[5:]),
            },
            "tie_break": "critical desc, high desc, total desc, label asc",
        },
        "exploitability": {
            **exploitability,
            "denominator": pending,
        },
        "malware": {**malware, "denominator": pending},
        "coverage": {
            "exploitability_known_ratio": ratio(
                exploitability["positive"] + exploitability["negative_no_info"], pending
            ),
            "malware_known_ratio": ratio(
                malware["positive"] + malware["negative_no_info"], pending
            ),
            "severity_known_ratio": ratio(total, total),
            "missing_fields": (
                [f"FQDN/DNS/NetBIOS/IP en {unknown_asset_rows} registros"]
                if unknown_asset_rows
                else []
            ),
        },
        "metric_versions": {
            "severity_scale": "1-5",
            "status_policy_version": snapshot.status_policy_version,
            "severity_policy_version": snapshot.severity_policy_version,
            "adapter_version": snapshot.adapter_version,
        },
    }
