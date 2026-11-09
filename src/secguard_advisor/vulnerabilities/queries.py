"""Consultas básicas de registros Qualys confirmados para findings_query."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_, select
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


def list_confirmed(session: Session, case_id: str) -> list[QualysImport]:
    return list(
        session.scalars(
            select(QualysImport)
            .where(QualysImport.case_id == case_id, QualysImport.status == "confirmed")
            .order_by(QualysImport.confirmed_sequence.desc())
        )
    )


def get_confirmed(session: Session, case_id: str, import_id: str) -> QualysImport | None:
    return session.scalar(
        select(QualysImport).where(
            QualysImport.id == import_id,
            QualysImport.case_id == case_id,
            QualysImport.status == "confirmed",
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
    if getattr(arguments, "severity_level", None) is not None:
        filters.append(QualysVulnerability.severity_level == arguments.severity_level)
    if getattr(arguments, "priority", None) is not None:
        filters.append(QualysVulnerability.priority_flag == arguments.priority)
    if getattr(arguments, "exploitability", None) is not None:
        filters.append(QualysVulnerability.exploitability_eval == arguments.exploitability)
    if getattr(arguments, "malware", None) is not None:
        filters.append(QualysVulnerability.malware_eval == arguments.malware)
    return filters


def _groups(session: Session, arguments: Any, filters: list) -> list[dict]:
    group_by = getattr(arguments, "group_by", None)
    if group_by == "asset":
        rows = session.execute(
            select(QualysVulnerability.asset_label, func.count())
            .where(*filters)
            .group_by(QualysVulnerability.asset_label)
            .order_by(QualysVulnerability.asset_label)
        ).all()
        return [{"key": key, "count": count} for key, count in rows]
    if group_by == "status":
        rows = session.execute(
            select(QualysVulnerability.status_group, func.count())
            .where(*filters)
            .group_by(QualysVulnerability.status_group)
            .order_by(QualysVulnerability.status_group)
        ).all()
        return [{"key": key, "count": count} for key, count in rows]
    if group_by == "priority":
        rows = session.execute(
            select(QualysVulnerability.priority_flag, func.count())
            .where(*filters)
            .group_by(QualysVulnerability.priority_flag)
            .order_by(QualysVulnerability.priority_flag.desc())
        ).all()
        return [
            {"key": "priority" if flag else "not_priority", "count": count} for flag, count in rows
        ]
    if group_by == "origin":
        total = (
            session.scalar(select(func.count()).select_from(QualysVulnerability).where(*filters))
            or 0
        )
        return [{"key": "imported", "count": total}]
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
    snapshot_id: str | None = None,
) -> dict:
    """Devuelve el bloque de una instantánea confirmada o un resultado vacío."""
    snapshot = resolve_snapshot(
        session,
        case_id,
        snapshot_id or getattr(arguments, "snapshot_id", None),
    )
    if snapshot is None:
        return {
            "origin": "imported",
            "snapshot": None,
            "status_group": status_group or "pending_known",
            "total": 0,
            "groups": [],
            "status_counts": {},
            "severity_counts": {},
            "exploitability_counts": {},
            "malware_counts": {},
            "priority_counts": {"both_positive": 0},
            "manual_review_rows": 0,
            "severity_scale": "project_1_5",
            "truncated": False,
            "empty_reason": "no_confirmed_import",
        }
    filters = _filters(case_id, snapshot, arguments, status_group)
    total = (
        session.scalar(select(func.count()).select_from(QualysVulnerability).where(*filters)) or 0
    )
    status_counts = dict(
        session.execute(
            select(QualysVulnerability.status_raw, func.count())
            .where(*filters)
            .group_by(QualysVulnerability.status_raw)
            .order_by(QualysVulnerability.status_raw)
        ).all()
    )
    severity_counts = dict(
        session.execute(
            select(QualysVulnerability.severity_level, func.count())
            .where(*filters)
            .group_by(QualysVulnerability.severity_level)
            .order_by(QualysVulnerability.severity_level)
        ).all()
    )
    exploitability_counts = dict(
        session.execute(
            select(QualysVulnerability.exploitability_eval, func.count())
            .where(*filters)
            .group_by(QualysVulnerability.exploitability_eval)
        ).all()
    )
    malware_counts = dict(
        session.execute(
            select(QualysVulnerability.malware_eval, func.count())
            .where(*filters)
            .group_by(QualysVulnerability.malware_eval)
        ).all()
    )
    both_positive = (
        session.scalar(
            select(func.count())
            .select_from(QualysVulnerability)
            .where(*filters, QualysVulnerability.priority_flag.is_(True))
        )
        or 0
    )
    manual_review_rows = (
        session.scalar(
            select(func.count())
            .select_from(QualysVulnerability)
            .where(
                *filters,
                or_(
                    QualysVulnerability.status_group == "manual_review",
                    QualysVulnerability.exploitability_eval == "indeterminate",
                    QualysVulnerability.malware_eval == "indeterminate",
                ),
            )
        )
        or 0
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
        "status_counts": {str(key): count for key, count in status_counts.items()},
        "severity_counts": {str(key): count for key, count in severity_counts.items()},
        "exploitability_counts": exploitability_counts,
        "malware_counts": malware_counts,
        "priority_counts": {"both_positive": both_positive},
        "manual_review_rows": manual_review_rows,
        "severity_scale": "project_1_5",
        "truncated": False,
    }
    if getattr(arguments, "detail", False):
        items = _items(session, arguments, filters, snapshot)
        result["items"] = items
        result["truncated"] = total > len(items)
    return result
