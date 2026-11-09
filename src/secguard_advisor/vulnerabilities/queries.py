"""Consultas básicas de registros Qualys confirmados para findings_query."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from secguard_advisor.db.models import (
    Finding,
    QualysImport,
    QualysVulnerability,
    QualysVulnerabilityCve,
)


class QualysQueryError(ValueError):
    """Error de argumentos o alcance de la consulta importada."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def has_synthetic(session: Session, case_id: str) -> bool:
    return bool(
        session.scalar(select(func.count()).select_from(Finding).where(Finding.case_id == case_id))
    )


def has_confirmed_imports(session: Session, case_id: str) -> bool:
    return bool(
        session.scalar(
            select(func.count())
            .select_from(QualysImport)
            .where(QualysImport.case_id == case_id, QualysImport.status == "confirmed")
        )
    )


def resolve_snapshot(
    session: Session,
    case_id: str,
    snapshot_id: str | None = None,
) -> QualysImport | None:
    if snapshot_id:
        snapshot = session.scalar(
            select(QualysImport).where(
                QualysImport.id == snapshot_id,
                QualysImport.case_id == case_id,
                QualysImport.status == "confirmed",
            )
        )
        if snapshot is None:
            raise QualysQueryError("snapshot_not_found", "La instantánea no existe en este caso.")
        return snapshot
    return session.scalar(
        select(QualysImport)
        .where(QualysImport.case_id == case_id, QualysImport.status == "confirmed")
        .order_by(QualysImport.confirmed_sequence.desc())
        .limit(1)
    )


def _filters(
    case_id: str, snapshot: QualysImport, arguments: Any, status_group: str | None
) -> list:
    filters = [
        QualysVulnerability.case_id == case_id,
        QualysVulnerability.import_id == snapshot.id,
    ]
    if status_group is not None:
        filters.append(QualysVulnerability.status_group == status_group)
    if getattr(arguments, "asset", None):
        filters.append(QualysVulnerability.asset_label == arguments.asset)
    if getattr(arguments, "qid", None):
        filters.append(QualysVulnerability.qid == arguments.qid)
    if getattr(arguments, "cve", None):
        filters.append(
            QualysVulnerability.id.in_(
                select(QualysVulnerabilityCve.vulnerability_id).where(
                    QualysVulnerabilityCve.cve == arguments.cve
                )
            )
        )
    return filters


def _groups(session: Session, arguments: Any, filters: list) -> list[dict]:
    if getattr(arguments, "group_by", None) == "asset":
        rows = session.execute(
            select(QualysVulnerability.asset_label, func.count())
            .where(*filters)
            .group_by(QualysVulnerability.asset_label)
            .order_by(QualysVulnerability.asset_label)
        ).all()
        return [{"key": key, "count": count} for key, count in rows]
    rows = session.execute(
        select(
            QualysVulnerability.severity_level,
            QualysVulnerability.severity_label,
            func.count(),
        )
        .where(*filters)
        .group_by(QualysVulnerability.severity_level, QualysVulnerability.severity_label)
        .order_by(QualysVulnerability.severity_level)
    ).all()
    return [{"key": str(level), "count": count, "label": label} for level, label, count in rows]


def _items(session: Session, arguments: Any, filters: list, snapshot: QualysImport) -> list[dict]:
    rows = list(
        session.scalars(
            select(QualysVulnerability)
            .where(*filters)
            .order_by(
                QualysVulnerability.severity_level.desc(),
                QualysVulnerability.asset_label,
                QualysVulnerability.row_number,
            )
            .limit(arguments.limit)
        )
    )
    ids = [row.id for row in rows]
    cves: dict[str, list[str]] = {row_id: [] for row_id in ids}
    if ids:
        for vulnerability_id, cve in session.execute(
            select(QualysVulnerabilityCve.vulnerability_id, QualysVulnerabilityCve.cve)
            .where(QualysVulnerabilityCve.vulnerability_id.in_(ids))
            .order_by(QualysVulnerabilityCve.cve)
        ).all():
            cves[vulnerability_id].append(cve)
    provenance = f"qualys:{snapshot.adapter_version}"
    return [
        {
            "vulnerability_id": row.id,
            "import_id": row.import_id,
            "row_number": row.row_number,
            "asset": row.asset_label,
            "title": row.title,
            "qid": row.qid,
            "status": row.status_raw,
            "status_group": row.status_group,
            "severity_level": row.severity_level,
            "severity_label": row.severity_label,
            "severity_raw": row.severity_raw,
            "priority": row.priority_flag,
            "priority_reason": row.priority_reason,
            "exploitability": row.exploitability_eval,
            "malware": row.malware_eval,
            "cves": cves[row.id],
            "first_detected": row.first_detected,
            "last_detected": row.last_detected,
            "provenance": provenance,
        }
        for row in rows
    ]


def imported_result(
    session: Session,
    case_id: str,
    arguments: Any,
    *,
    status_group: str | None,
) -> dict:
    """Devuelve el bloque de una instantánea confirmada o un resultado vacío."""
    snapshot = resolve_snapshot(session, case_id, getattr(arguments, "snapshot_id", None))
    if snapshot is None:
        return {
            "origin": "imported",
            "snapshot": None,
            "status_group": status_group or "pending_known",
            "total": 0,
            "groups": [],
            "severity_scale": "project_1_5",
            "priority_counts": {},
            "truncated": False,
            "empty_reason": "no_confirmed_import",
        }
    filters = _filters(case_id, snapshot, arguments, status_group)
    total = (
        session.scalar(select(func.count()).select_from(QualysVulnerability).where(*filters)) or 0
    )
    result = {
        "origin": "imported",
        "snapshot": {
            "id": snapshot.id,
            "sequence": snapshot.confirmed_sequence,
            "confirmed_at": snapshot.confirmed_at,
            "csv_sha256": snapshot.csv_sha256,
            "adapter_version": snapshot.adapter_version,
        },
        "status_group": status_group or "all",
        "total": total,
        "groups": _groups(session, arguments, filters),
        "severity_scale": "project_1_5",
        "priority_counts": json.loads(snapshot.priority_counts_json),
        "truncated": False,
    }
    if getattr(arguments, "detail", False):
        items = _items(session, arguments, filters, snapshot)
        result["items"] = items
        result["truncated"] = total > len(items)
    return result
