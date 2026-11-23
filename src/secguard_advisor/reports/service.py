"""Report generation, immutable versions and artifact lookup."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from secguard_advisor.config import Settings
from secguard_advisor.db.models import Case, QualysImport, Report, ReportArtifact, ReportVersion
from secguard_advisor.reports.artifacts import (
    read_artifact,
    relative_artifact_path,
    version_directory,
    write_artifact,
)
from secguard_advisor.reports.canonical import canonical_json, parse_json
from secguard_advisor.reports.charts import build_chart_specs
from secguard_advisor.reports.dataset import build_dataset
from secguard_advisor.reports.errors import report_error
from secguard_advisor.reports.metrics import ReportFilters
from secguard_advisor.reports.render import render_charts, render_pdf, render_print_html
from secguard_advisor.reports.synthesis import synthesize_report


@dataclass(frozen=True, slots=True)
class ReportVersionResult:
    report_id: str
    version_id: str
    version_number: int
    dataset_sha256: str
    synthesis_status: str


def _confirmed_snapshot(session: Session, case_id: str, snapshot_id: str) -> QualysImport:
    snapshot = session.scalar(
        select(QualysImport).where(
            QualysImport.id == snapshot_id,
            QualysImport.case_id == case_id,
            QualysImport.status == "confirmed",
        )
    )
    if snapshot is None:
        raise report_error("snapshot_not_found")
    return snapshot


def _ensure_report(session: Session, case_id: str, author: str) -> Report:
    report = session.scalar(
        select(Report).where(Report.case_id == case_id).order_by(Report.created_at.desc())
    )
    if report is None:
        report = Report(case_id=case_id, created_by=author)
        session.add(report)
        session.flush()
    return report


def _summary_payload(
    *,
    report_id: str,
    version: ReportVersion,
    synthesis: dict[str, Any],
) -> dict[str, Any]:
    return {
        "report_id": report_id,
        "version_id": version.id,
        "version_number": version.version_number,
        "created_at": version.created_at,
        "dataset_sha256": version.dataset_sha256,
        "summary_text": synthesis["summary"]["text"],
        "focus": synthesis["focus"],
        "recommendations": synthesis["recommendations"],
        "limitations": synthesis["limitations"],
    }


def create_report_version(
    session: Session,
    settings: Settings,
    *,
    case_id: str,
    snapshot_id: str,
    filters: ReportFilters | None = None,
    author: str,
    synthesize: bool = False,
    generation_key: str | None = None,
    synthesis_generator: Any | None = None,
    chart_renderer: Callable[[Settings, dict], dict[str, str]] = render_charts,
    pdf_renderer: Callable[[Settings, str, Path], bytes] = render_pdf,
) -> ReportVersionResult:
    """Create or recover one immutable report version."""
    if generation_key:
        existing = session.scalar(
            select(ReportVersion).where(ReportVersion.generation_key == generation_key)
        )
        if existing is not None:
            return ReportVersionResult(
                existing.report_id,
                existing.id,
                existing.version_number,
                existing.dataset_sha256,
                existing.synthesis_status,
            )
    case = session.get(Case, case_id)
    if case is None:
        raise report_error("snapshot_not_found")
    snapshot = _confirmed_snapshot(session, case_id, snapshot_id)
    dataset, dataset_sha256 = build_dataset(
        session, case=case, snapshot=snapshot, filters=filters or ReportFilters()
    )
    report = _ensure_report(session, case_id, author)
    max_version = session.scalar(
        select(func.max(ReportVersion.version_number)).where(ReportVersion.report_id == report.id)
    )
    version_number = int(max_version or 0) + 1
    version = ReportVersion(
        report_id=report.id,
        case_id=case_id,
        version_number=version_number,
        generation_key=generation_key,
        snapshot_import_id=snapshot.id,
        snapshot_sequence=int(snapshot.confirmed_sequence or 1),
        filters_json=canonical_json((filters or ReportFilters()).as_dict()),
        dataset_json=canonical_json(dataset),
        dataset_sha256=dataset_sha256,
        chart_specs_json=canonical_json({}),
        synthesis_status="not_requested",
        summary_text="",
        focus_json="[]",
        recommendations_json="[]",
        limitations_json="[]",
        author_declared=author,
    )
    session.add(version)
    session.flush()

    charts = build_chart_specs(dataset)
    chart_svgs = chart_renderer(settings, charts)
    synthesis = synthesize_report(
        session,
        settings,
        case_id=case_id,
        dataset=dataset,
        enabled=synthesize,
        generator=synthesis_generator,
    )
    summary = _summary_payload(report_id=report.id, version=version, synthesis=synthesis.payload)
    html = render_print_html(
        settings,
        dataset={**dataset, "sha256": dataset_sha256},
        charts=charts,
        chart_svgs=chart_svgs,
        summary=summary,
    )
    directory = version_directory(settings, case_id, report.id, version_number)
    directory.mkdir(parents=True, exist_ok=True)
    pdf_temp = directory / ".informe-ejecutivo.pdf.tmp"
    pdf_bytes = pdf_renderer(settings, html, pdf_temp)
    pdf_temp.unlink(missing_ok=True)
    if not pdf_bytes.startswith(b"%PDF"):
        raise report_error("pdf_render_failed")

    version.chart_specs_json = canonical_json(charts)
    version.synthesis_status = synthesis.status
    version.ai_run_id = synthesis.run_id
    version.summary_text = synthesis.payload["summary"]["text"]
    version.focus_json = canonical_json(synthesis.payload["focus"])
    version.recommendations_json = canonical_json(synthesis.payload["recommendations"])
    version.limitations_json = canonical_json(synthesis.payload["limitations"])

    for key, svg in chart_svgs.items():
        relative = relative_artifact_path(case_id, report.id, version_number, f"chart-{key}.svg")
        digest, size = write_artifact(settings, relative, svg.encode("utf-8"))
        session.add(
            ReportArtifact(
                report_version_id=version.id,
                kind="chart_svg",
                chart_key=key,
                relative_path=relative,
                sha256=digest,
                bytes=size,
            )
        )
    pdf_relative = relative_artifact_path(
        case_id, report.id, version_number, "informe-ejecutivo.pdf"
    )
    pdf_digest, pdf_size = write_artifact(settings, pdf_relative, pdf_bytes)
    session.add(
        ReportArtifact(
            report_version_id=version.id,
            kind="pdf",
            chart_key="",
            relative_path=pdf_relative,
            sha256=pdf_digest,
            bytes=pdf_size,
        )
    )
    session.flush()
    return ReportVersionResult(
        report.id, version.id, version.version_number, dataset_sha256, synthesis.status
    )


def list_versions(session: Session, case_id: str) -> list[ReportVersion]:
    return list(
        session.scalars(
            select(ReportVersion)
            .where(ReportVersion.case_id == case_id)
            .order_by(ReportVersion.created_at.desc())
        )
    )


def get_version(
    session: Session, case_id: str, report_id: str, version_number: int
) -> ReportVersion:
    version = session.scalar(
        select(ReportVersion).where(
            ReportVersion.case_id == case_id,
            ReportVersion.report_id == report_id,
            ReportVersion.version_number == version_number,
        )
    )
    if version is None:
        raise report_error("version_not_found")
    return version


def get_pdf_artifact(session: Session, version: ReportVersion) -> ReportArtifact:
    artifact = session.scalar(
        select(ReportArtifact).where(
            ReportArtifact.report_version_id == version.id,
            ReportArtifact.kind == "pdf",
        )
    )
    if artifact is None:
        raise report_error("pdf_not_ready")
    return artifact


def preview_html(session: Session, settings: Settings, version: ReportVersion) -> str:
    dataset = parse_json(version.dataset_json)
    dataset["sha256"] = version.dataset_sha256
    charts = parse_json(version.chart_specs_json)
    chart_svgs: dict[str, str] = {}
    for artifact in session.scalars(
        select(ReportArtifact).where(
            ReportArtifact.report_version_id == version.id,
            ReportArtifact.kind == "chart_svg",
        )
    ):
        chart_svgs[artifact.chart_key] = read_artifact(settings, artifact.relative_path).decode(
            "utf-8"
        )
    summary = {
        "report_id": version.report_id,
        "version_id": version.id,
        "version_number": version.version_number,
        "created_at": version.created_at,
        "dataset_sha256": version.dataset_sha256,
        "summary_text": version.summary_text,
        "focus": parse_json(version.focus_json),
        "recommendations": parse_json(version.recommendations_json),
        "limitations": parse_json(version.limitations_json),
    }
    return render_print_html(
        settings, dataset=dataset, charts=charts, chart_svgs=chart_svgs, summary=summary
    )
