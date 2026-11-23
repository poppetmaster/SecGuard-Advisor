"""Report generation, immutable versions and artifact lookup."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from secguard_advisor.config import Settings
from secguard_advisor.conversation.concurrency import GenerationSlot
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


def _result(version: ReportVersion) -> ReportVersionResult:
    return ReportVersionResult(
        version.report_id,
        version.id,
        version.version_number,
        version.dataset_sha256,
        version.synthesis_status,
    )


def _cleanup_version(
    session: Session, settings: Settings, version: ReportVersion, *, delete_rows: bool = True
) -> None:
    """Remove only this version's artifacts; never touch a ready prior version."""
    for artifact in list(
        session.scalars(
            select(ReportArtifact).where(ReportArtifact.report_version_id == version.id)
        )
    ):
        (settings.reports_dir / artifact.relative_path).unlink(missing_ok=True)
        if delete_rows:
            session.delete(artifact)
    shutil.rmtree(
        version_directory(settings, version.case_id, version.report_id, version.version_number),
        ignore_errors=True,
    )
    shutil.rmtree(settings.reports_dir / ".tmp" / version.id, ignore_errors=True)


def _reserve_version(
    session: Session,
    settings: Settings,
    *,
    case: Case,
    snapshot: QualysImport,
    filters: ReportFilters,
    author: str,
    generation_key: str | None,
) -> ReportVersion:
    if generation_key:
        existing = session.scalar(
            select(ReportVersion).where(ReportVersion.generation_key == generation_key)
        )
        if existing is not None:
            if existing.case_id != case.id:
                raise report_error("generation_key_conflict")
            if existing.snapshot_import_id != snapshot.id:
                raise report_error("generation_key_conflict")
            if existing.status == "ready":
                return existing
            _cleanup_version(session, settings, existing)
            existing.status = "generating"
            session.commit()
            return existing

    for attempt in range(2):
        report = _ensure_report(session, case.id, author)
        max_version = session.scalar(
            select(func.max(ReportVersion.version_number)).where(
                ReportVersion.report_id == report.id
            )
        )
        version_number = int(max_version or 0) + 1
        version = ReportVersion(
            report_id=report.id,
            case_id=case.id,
            version_number=version_number,
            status="generating",
            generation_key=generation_key,
            snapshot_import_id=snapshot.id,
            snapshot_sequence=int(snapshot.confirmed_sequence or 1),
            filters_json=canonical_json(filters.as_dict()),
            dataset_json="{}",
            dataset_sha256="",
            chart_specs_json="{}",
            synthesis_status="not_requested",
            summary_text="",
            focus_json="[]",
            recommendations_json="[]",
            limitations_json="[]",
            author_declared=author,
        )
        session.add(version)
        try:
            session.commit()
            return version
        except IntegrityError:
            session.rollback()
            if attempt == 1:
                raise
            if generation_key:
                existing = session.scalar(
                    select(ReportVersion).where(ReportVersion.generation_key == generation_key)
                )
                if existing is not None and existing.case_id == case.id:
                    if existing.status == "ready":
                        return existing
                    _cleanup_version(session, settings, existing)
                    existing.status = "generating"
                    session.commit()
                    return existing
    raise report_error("generation_conflict", status=409)


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
    session_factory: sessionmaker[Session] | None = None,
    generation_slot: GenerationSlot | None = None,
) -> ReportVersionResult:
    """Create or recover one immutable report version with short transactions."""
    factory = session_factory or sessionmaker(bind=session.get_bind(), expire_on_commit=False)
    if generation_slot is not None and not generation_slot.acquire(timeout=0):
        raise report_error("generation_busy", status=409)
    version: ReportVersion | None = None
    try:
        case = session.get(Case, case_id)
        if case is None:
            raise report_error("snapshot_not_found")
        snapshot = _confirmed_snapshot(session, case_id, snapshot_id)
        active_filters = filters or ReportFilters()
        version = _reserve_version(
            session,
            settings,
            case=case,
            snapshot=snapshot,
            filters=active_filters,
            author=author,
            generation_key=generation_key,
        )
        if version.status == "ready":
            return _result(version)

        dataset, dataset_sha256 = build_dataset(
            session, case=case, snapshot=snapshot, filters=active_filters
        )
        session.commit()

        charts = build_chart_specs(dataset)
        chart_svgs = chart_renderer(settings, charts)
        synthesis = synthesize_report(
            factory,
            settings,
            case_id=case_id,
            dataset=dataset,
            enabled=synthesize,
            generator=synthesis_generator,
        )
        summary = _summary_payload(
            report_id=version.report_id, version=version, synthesis=synthesis.payload
        )
        html = render_print_html(
            settings,
            dataset={**dataset, "sha256": dataset_sha256},
            charts=charts,
            chart_svgs=chart_svgs,
            summary=summary,
        )

        temp_dir = settings.reports_dir / ".tmp" / version.id
        shutil.rmtree(temp_dir, ignore_errors=True)
        temp_dir.mkdir(parents=True, exist_ok=True)
        pdf_bytes = pdf_renderer(settings, html, temp_dir / "informe-ejecutivo.pdf")
        if not pdf_bytes.startswith(b"%PDF"):
            raise report_error("pdf_render_failed")

        final_dir = version_directory(settings, case_id, version.report_id, version.version_number)
        shutil.rmtree(final_dir, ignore_errors=True)
        final_dir.mkdir(parents=True, exist_ok=True)
        artifacts: list[ReportArtifact] = []
        for key, svg in chart_svgs.items():
            relative = relative_artifact_path(
                case_id, version.report_id, version.version_number, f"chart-{key}.svg"
            )
            digest, size = write_artifact(settings, relative, svg.encode("utf-8"))
            artifacts.append(
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
            case_id, version.report_id, version.version_number, "informe-ejecutivo.pdf"
        )
        pdf_digest, pdf_size = write_artifact(settings, pdf_relative, pdf_bytes)
        artifacts.append(
            ReportArtifact(
                report_version_id=version.id,
                kind="pdf",
                chart_key="",
                relative_path=pdf_relative,
                sha256=pdf_digest,
                bytes=pdf_size,
            )
        )

        version = session.get(ReportVersion, version.id)
        version.chart_specs_json = canonical_json(charts)
        version.synthesis_status = synthesis.status
        version.ai_run_id = synthesis.run_id
        version.summary_text = synthesis.payload["summary"]["text"]
        version.focus_json = canonical_json(synthesis.payload["focus"])
        version.recommendations_json = canonical_json(synthesis.payload["recommendations"])
        version.limitations_json = canonical_json(synthesis.payload["limitations"])
        version.dataset_json = canonical_json(dataset)
        version.dataset_sha256 = dataset_sha256
        version.status = "ready"
        session.add_all(artifacts)
        session.commit()
        shutil.rmtree(temp_dir, ignore_errors=True)
        return _result(version)
    except Exception:
        session.rollback()
        if version is not None:
            try:
                with factory() as cleanup_session:
                    failed = cleanup_session.get(ReportVersion, version.id)
                    if failed is not None and failed.status != "ready":
                        failed.status = "failed"
                        _cleanup_version(cleanup_session, settings, failed)
                        cleanup_session.commit()
            except Exception:
                pass
        raise
    finally:
        if generation_slot is not None:
            generation_slot.release()


def list_versions(session: Session, case_id: str) -> list[ReportVersion]:
    return list(
        session.scalars(
            select(ReportVersion)
            .where(ReportVersion.case_id == case_id, ReportVersion.status == "ready")
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
            ReportVersion.status == "ready",
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
