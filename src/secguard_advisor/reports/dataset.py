"""Canonical immutable dataset for one report version."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from secguard_advisor.db.models import Case, QualysImport
from secguard_advisor.reports.aliasing import apply_asset_aliases
from secguard_advisor.reports.canonical import canonical_sha256
from secguard_advisor.reports.errors import report_error
from secguard_advisor.reports.metrics import ReportFilters, build_metrics
from secguard_advisor.reports.privacy import DEFAULT_CONTENT_POLICY


def build_dataset(
    session: Session,
    *,
    case: Case,
    snapshot: QualysImport,
    filters: ReportFilters | None = None,
) -> tuple[dict[str, Any], str]:
    """Build the dataset and its canonical SHA-256 from SQLite."""
    if snapshot.case_id != case.id or snapshot.status != "confirmed":
        raise report_error("snapshot_not_confirmed")
    active = filters or ReportFilters()
    metric_block = build_metrics(session, case_id=case.id, snapshot=snapshot, filters=active)
    dataset: dict[str, Any] = {
        "schema_version": "report-dataset-v1",
        "case": {
            "id": case.id,
            "title": case.title,
            "scope": case.ai_application,
            "is_synthetic": case.context_is_synthetic,
            "synthetic_notice": case.synthetic_notice,
        },
        "snapshot": {
            "import_id": snapshot.id,
            "sequence": snapshot.confirmed_sequence,
            "confirmed_at": snapshot.confirmed_at,
            "csv_sha256": snapshot.csv_sha256,
            "row_count": snapshot.row_count,
            "valid_rows": snapshot.valid_rows,
            "invalid_rows": snapshot.invalid_rows,
            "warning_rows": snapshot.warning_rows,
            "manifest_status": snapshot.manifest_status,
            "origin": "imported",
            "provenance": snapshot.provenance,
        },
        "content_policy": dict(DEFAULT_CONTENT_POLICY),
        "filters": active.as_dict(),
        "base": metric_block["base"],
        "cards": metric_block["cards"],
        "severity": metric_block["severity"],
        "assets_top": apply_asset_aliases(metric_block["assets_top"]),
        "exploitability": metric_block["exploitability"],
        "malware": metric_block["malware"],
        "coverage": metric_block["coverage"],
        "limitations": [
            "Los indicadores vacíos se muestran como no informados; no son negativos.",
            "Un total 0 no demuestra ausencia de vulnerabilidades.",
            "Los conteos no se multiplican por CVE; los indicadores solapados no se suman.",
            "Fixed es un antecedente histórico y no una remediación pendiente.",
        ],
        "metric_versions": metric_block["metric_versions"],
    }
    return dataset, canonical_sha256(dataset)
