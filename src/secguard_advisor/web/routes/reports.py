"""Informe ejecutivo: generación, vista, PDF e historial."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from sqlalchemy import select

from secguard_advisor.cases.scope import CaseNotFoundError, require_case, resolve_case_scope
from secguard_advisor.db.models import ReportArtifact
from secguard_advisor.reports.canonical import parse_json
from secguard_advisor.reports.errors import ReportError
from secguard_advisor.reports.metrics import ReportFilters
from secguard_advisor.reports.service import (
    create_report_version,
    get_pdf_artifact,
    get_version,
    list_versions,
    preview_html,
)
from secguard_advisor.vulnerabilities.queries import list_confirmed
from secguard_advisor.web.navigation import Crumb, case_crumbs, page

router = APIRouter(tags=["reports"])


def _templates(request: Request):
    return request.app.state.templates


def _not_found(request: Request, message: str = "No encontrado en este caso."):
    return _templates(request).TemplateResponse(
        request=request, name="errors/404.html", context={"message": message}, status_code=404
    )


def _case(request: Request, case_id: str):
    with request.app.state.session_factory() as session:
        scope = resolve_case_scope(session, case_id)
        case = require_case(session, scope)
        return case.id, case.title


def _filters_from_form(
    asset: str,
    qid: str,
    cve: str,
    severity_level: str,
    exploitability: str,
    malware: str,
    priority: str,
    status_group: str,
) -> ReportFilters:
    def _int(value: str) -> int | None:
        try:
            return int(value) if value else None
        except ValueError:
            return None

    return ReportFilters(
        asset=asset.strip() or None,
        qid=qid.strip() or None,
        cve=cve.strip() or None,
        severity_level=_int(severity_level),
        exploitability=exploitability or None,
        malware=malware or None,
        priority=True if priority == "true" else False if priority == "false" else None,
        status_group=status_group or None,
    )


def _summary(session, version):
    return {
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


@router.get("/cases/{case_id}/reports", response_class=HTMLResponse)
def reports_index(request: Request, case_id: str):
    try:
        case_id, case_title = _case(request, case_id)
    except CaseNotFoundError:
        return _not_found(request)
    with request.app.state.session_factory() as session:
        versions = list_versions(session, case_id)
        snapshots = list_confirmed(session, case_id)
        latest = snapshots[0] if snapshots else None
    return _templates(request).TemplateResponse(
        request=request,
        name="reports/index.html",
        context={
            "case_id": case_id,
            "versions": versions,
            "snapshots": snapshots,
            "latest": latest,
            "wide": True,
            **page(
                title="Informe ejecutivo",
                section="reports",
                case_id=case_id,
                case_title=case_title,
                crumbs=case_crumbs(case_id, case_title, Crumb("Informe ejecutivo")),
            ),
        },
    )


@router.get("/cases/{case_id}/reports/new", response_class=HTMLResponse)
def reports_new(request: Request, case_id: str):
    try:
        case_id, case_title = _case(request, case_id)
    except CaseNotFoundError:
        return _not_found(request)
    with request.app.state.session_factory() as session:
        snapshots = list_confirmed(session, case_id)
        latest = snapshots[0] if snapshots else None
    return _templates(request).TemplateResponse(
        request=request,
        name="reports/new.html",
        context={
            "case_id": case_id,
            "snapshots": snapshots,
            "latest": latest,
            "values": {},
            "wide": True,
            **page(
                title="Generar informe ejecutivo",
                section="reports",
                case_id=case_id,
                case_title=case_title,
                crumbs=case_crumbs(
                    case_id,
                    case_title,
                    Crumb("Informe ejecutivo", f"/cases/{case_id}/reports"),
                    Crumb("Nuevo"),
                ),
            ),
        },
    )


@router.post("/cases/{case_id}/reports", response_class=HTMLResponse)
def reports_create(
    request: Request,
    case_id: str,
    snapshot_id: str = Form(""),
    author: str = Form(""),
    synthesize: str = Form(""),
    asset: str = Form(""),
    qid: str = Form(""),
    cve: str = Form(""),
    severity_level: str = Form(""),
    exploitability: str = Form(""),
    malware: str = Form(""),
    priority: str = Form(""),
    status_group: str = Form(""),
):
    try:
        case_id, case_title = _case(request, case_id)
    except CaseNotFoundError:
        return _not_found(request)
    filters = _filters_from_form(
        asset, qid, cve, severity_level, exploitability, malware, priority, status_group
    )
    values = {
        "snapshot_id": snapshot_id,
        "author": author,
        "synthesize": synthesize,
        "asset": asset,
        "qid": qid,
        "cve": cve,
        "severity_level": severity_level,
        "exploitability": exploitability,
        "malware": malware,
        "priority": priority,
        "status_group": status_group,
    }
    try:
        with request.app.state.session_factory() as session:
            result = create_report_version(
                session,
                request.app.state.settings,
                case_id=case_id,
                snapshot_id=snapshot_id,
                filters=filters,
                author=author.strip() or "Responsable no declarado",
                synthesize=synthesize == "on",
                session_factory=request.app.state.session_factory,
                generation_slot=request.app.state.generation_slot,
            )
            session.commit()
    except ReportError as exc:
        with request.app.state.session_factory() as session:
            snapshots = list_confirmed(session, case_id)
        return _templates(request).TemplateResponse(
            request=request,
            name="reports/new.html",
            context={
                "case_id": case_id,
                "snapshots": snapshots,
                "latest": snapshots[0] if snapshots else None,
                "values": values,
                "error": exc.message,
                "wide": True,
                **page(
                    title="Generar informe ejecutivo",
                    section="reports",
                    case_id=case_id,
                    case_title=case_title,
                ),
            },
            status_code=exc.status,
        )
    target = f"/cases/{case_id}/reports/{result.report_id}/versions/{result.version_number}"
    return RedirectResponse(url=target, status_code=303)


@router.get(
    "/cases/{case_id}/reports/{report_id}/versions/{version_number}", response_class=HTMLResponse
)
def reports_view(request: Request, case_id: str, report_id: str, version_number: int):
    try:
        case_id, case_title = _case(request, case_id)
    except CaseNotFoundError:
        return _not_found(request)
    with request.app.state.session_factory() as session:
        try:
            version = get_version(session, case_id, report_id, version_number)
        except ReportError:
            return _not_found(request)
        summary = _summary(session, version)
        dataset = parse_json(version.dataset_json)
        dataset["sha256"] = version.dataset_sha256
        charts = parse_json(version.chart_specs_json)
        artifacts = list(
            session.scalars(
                select(ReportArtifact).where(ReportArtifact.report_version_id == version.id)
            )
        )
        pdf_ready = any(item.kind == "pdf" for item in artifacts)
        versions = list_versions(session, case_id)
    return _templates(request).TemplateResponse(
        request=request,
        name="reports/view.html",
        context={
            "case_id": case_id,
            "report_id": report_id,
            "version": version,
            "summary": summary,
            "dataset": dataset,
            "charts": charts,
            "pdf_ready": pdf_ready,
            "versions": versions,
            "wide": True,
            **page(
                title=f"Informe ejecutivo · versión {version_number}",
                section="reports",
                case_id=case_id,
                case_title=case_title,
                crumbs=case_crumbs(
                    case_id,
                    case_title,
                    Crumb("Informe ejecutivo", f"/cases/{case_id}/reports"),
                    Crumb(f"Versión {version_number}"),
                ),
            ),
        },
    )


@router.get("/cases/{case_id}/reports/{report_id}/versions/{version_number}/pdf")
def reports_pdf(request: Request, case_id: str, report_id: str, version_number: int):
    try:
        _case(request, case_id)
    except CaseNotFoundError:
        return _not_found(request)
    with request.app.state.session_factory() as session:
        try:
            version = get_version(session, case_id, report_id, version_number)
            artifact = get_pdf_artifact(session, version)
        except ReportError:
            return Response(status_code=409, content="El PDF no está disponible.")
        path = request.app.state.settings.reports_dir / artifact.relative_path
    if not path.exists():
        return Response(status_code=409, content="El PDF no está disponible.")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"informe-ejecutivo-v{version_number}.pdf",
    )


@router.get("/cases/{case_id}/reports/{report_id}/versions/{version_number}/preview")
def reports_preview(request: Request, case_id: str, report_id: str, version_number: int):
    try:
        _case(request, case_id)
    except CaseNotFoundError:
        return _not_found(request)
    with request.app.state.session_factory() as session:
        try:
            version = get_version(session, case_id, report_id, version_number)
            html = preview_html(session, request.app.state.settings, version)
        except ReportError:
            return _not_found(request)
    return HTMLResponse(html)
