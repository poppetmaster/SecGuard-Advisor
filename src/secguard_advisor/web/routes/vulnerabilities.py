"""Rutas de «Vulnerabilidades»: carga, validación, preview, confirmación y consulta."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import func, select

from secguard_advisor.cases.scope import CaseNotFoundError, require_case, resolve_case_scope
from secguard_advisor.db.models import (
    QualysImport,
    QualysImportIssue,
    QualysVulnerability,
    QualysVulnerabilityCve,
)
from secguard_advisor.vulnerabilities.queries import get_confirmed, list_confirmed
from secguard_advisor.vulnerabilities.service import (
    ImportNotFoundError,
    InvalidTransitionError,
    QualysImportService,
)
from secguard_advisor.web.navigation import Crumb, case_crumbs, page

router = APIRouter(tags=["vulnerabilities"])

STATUS_LABELS = {
    "validating": "Validando",
    "staged": "Listo para confirmar",
    "rejected": "Rechazado",
    "confirmed": "Confirmado",
    "cancelled": "Cancelado",
    "expired": "Expirado",
    "failed": "Fallido",
}
SEVERITY_LABELS = {
    "1": "Informativa",
    "2": "Baja",
    "3": "Media",
    "4": "Alta",
    "5": "Crítica",
}
MANIFEST_LABELS = {
    "absent": "Sin manifiesto",
    "matched": "Manifiesto coincidente",
    "mismatch": "Manifiesto no coincidente",
    "invalid": "Manifiesto inválido",
}
NOTICES = {
    "confirmed": "Importación confirmada. La instantánea ya está disponible.",
    "idempotent": "La importación ya estaba confirmada; no se duplicaron registros.",
    "cancelled": "Importación cancelada. La instantánea vigente no cambió.",
}
MAX_PREVIEW_ROWS = 50
MAX_ISSUES = 30


class UploadRejected(ValueError):
    def __init__(self, code: str, message: str, status: int) -> None:
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


def _templates(request: Request):
    return request.app.state.templates


def _is_htmx(request: Request) -> bool:
    return request.headers.get("hx-request", "").lower() == "true"


def _not_found(request: Request):
    return _templates(request).TemplateResponse(
        request=request,
        name="errors/404.html",
        context={"message": "No encontrado en este caso."},
        status_code=404,
    )


def _case_header(request: Request, case_id: str) -> tuple[str, str]:
    with request.app.state.session_factory() as session:
        scope = resolve_case_scope(session, case_id)
        case = require_case(session, scope)
        return case.id, case.title


def _summary(record: QualysImport | None) -> dict | None:
    if record is None:
        return None
    return {
        "row_count": record.row_count,
        "valid_rows": record.valid_rows,
        "invalid_rows": record.invalid_rows,
        "warning_rows": record.warning_rows,
        "manual_review_rows": record.manual_review_rows,
        "status_counts": json.loads(record.status_counts_json),
        "severity_counts": json.loads(record.severity_counts_json),
        "exploitability_counts": json.loads(record.exploitability_counts_json),
        "malware_counts": json.loads(record.malware_counts_json),
        "priority_counts": json.loads(record.priority_counts_json),
        "possible_repeat_groups": record.possible_repeat_groups,
        "possible_repeat_rows": record.possible_repeat_rows,
        "manifest_status": record.manifest_status,
    }


def _rows(session, import_id: str) -> list[dict]:
    rows = list(
        session.scalars(
            select(QualysVulnerability)
            .where(QualysVulnerability.import_id == import_id)
            .order_by(
                QualysVulnerability.severity_level.desc(),
                QualysVulnerability.asset_label,
                QualysVulnerability.row_number,
            )
            .limit(MAX_PREVIEW_ROWS)
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
    return [
        {
            "id": row.id,
            "asset": row.asset_label,
            "title": row.title,
            "qid": row.qid,
            "status": row.status_raw,
            "status_group": row.status_group,
            "severity_level": row.severity_level,
            "severity_label": row.severity_label,
            "priority": row.priority_flag,
            "priority_reason": row.priority_reason,
            "exploitability": row.exploitability_eval,
            "malware": row.malware_eval,
            "cves": cves[row.id],
            "first_detected": row.first_detected,
            "last_detected": row.last_detected,
        }
        for row in rows
    ]


def _issues(session, import_id: str) -> tuple[list[QualysImportIssue], dict[str, int]]:
    rows = list(
        session.scalars(
            select(QualysImportIssue)
            .where(QualysImportIssue.import_id == import_id)
            .order_by(
                QualysImportIssue.severity, QualysImportIssue.row_number, QualysImportIssue.id
            )
            .limit(MAX_ISSUES)
        )
    )
    counts = dict(
        session.execute(
            select(QualysImportIssue.severity, func.count())
            .where(QualysImportIssue.import_id == import_id)
            .group_by(QualysImportIssue.severity)
        ).all()
    )
    return rows, counts


def _latest_confirmed(session, case_id: str) -> QualysImport | None:
    return session.scalar(
        select(QualysImport)
        .where(QualysImport.case_id == case_id, QualysImport.status == "confirmed")
        .order_by(QualysImport.confirmed_sequence.desc())
        .limit(1)
    )


def _load_import(session, case_id: str, import_id: str) -> QualysImport | None:
    record = session.get(QualysImport, import_id)
    if record is None or record.case_id != case_id:
        return None
    return record


def _history(session, case_id: str) -> list[QualysImport]:
    return list(
        session.scalars(
            select(QualysImport)
            .where(QualysImport.case_id == case_id)
            .order_by(QualysImport.created_at.desc())
            .limit(50)
        )
    )


def _section_context(
    request: Request,
    case_id: str,
    case_title: str,
    *,
    import_id: str | None = None,
    notice: str | None = None,
    errors: dict[str, str] | None = None,
) -> dict:
    with request.app.state.session_factory() as session:
        snapshots = list_confirmed(session, case_id)
        if import_id is not None:
            selected = get_confirmed(session, case_id, import_id)
            if selected is None:
                raise LookupError(import_id)
        else:
            selected = snapshots[0] if snapshots else None
        rows = _rows(session, selected.id) if selected is not None else []
    latest_id = snapshots[0].id if snapshots else None
    return {
        "case_id": case_id,
        "case_title": case_title,
        "record": selected,
        "summary": _summary(selected),
        "rows": rows,
        "rows_truncated": bool(selected and selected.row_count > len(rows)),
        "snapshots": snapshots,
        "selected_id": selected.id if selected is not None else None,
        "latest_id": latest_id,
        "is_latest": selected is not None and selected.id == latest_id,
        "notice": notice,
        "errors": errors or {},
        "status_labels": STATUS_LABELS,
        "severity_labels": SEVERITY_LABELS,
        "manifest_labels": MANIFEST_LABELS,
        **page(
            title="Vulnerabilidades",
            section="vulnerabilities",
            case_id=case_id,
            case_title=case_title,
            crumbs=case_crumbs(case_id, case_title, Crumb("Vulnerabilidades")),
        ),
    }


def _render_section(
    request: Request,
    case_id: str,
    case_title: str,
    *,
    import_id: str | None = None,
    status_code: int = 200,
    notice: str | None = None,
    errors: dict[str, str] | None = None,
):
    context = _section_context(
        request,
        case_id,
        case_title,
        import_id=import_id,
        notice=notice,
        errors=errors,
    )
    name = "vulnerabilities/_panel.html" if _is_htmx(request) else "vulnerabilities/index.html"
    return _templates(request).TemplateResponse(
        request=request, name=name, context=context, status_code=status_code
    )


def _render_form(
    request: Request,
    case_id: str,
    case_title: str,
    *,
    status_code: int = 200,
    errors: dict[str, str] | None = None,
):
    context = {
        "case_id": case_id,
        "errors": errors or {},
        **page(
            title="Cargar reporte de Qualys",
            section="vulnerabilities",
            case_id=case_id,
            case_title=case_title,
            crumbs=case_crumbs(
                case_id,
                case_title,
                Crumb("Vulnerabilidades", f"/cases/{case_id}/vulnerabilities"),
                Crumb("Cargar reporte"),
            ),
        ),
    }
    name = "vulnerabilities/_form.html" if _is_htmx(request) else "vulnerabilities/form.html"
    return _templates(request).TemplateResponse(
        request=request, name=name, context=context, status_code=status_code
    )


def _render_preview(
    request: Request,
    case_id: str,
    case_title: str,
    record: QualysImport,
    *,
    status_code: int = 200,
    notice: str | None = None,
    error: str | None = None,
):
    with request.app.state.session_factory() as session:
        rows = _rows(session, record.id)
        issues, issue_counts = _issues(session, record.id)
    context = {
        "case_id": case_id,
        "case_title": case_title,
        "record": record,
        "summary": _summary(record),
        "rows": rows,
        "rows_truncated": bool(record.row_count > len(rows)),
        "issues": issues,
        "issue_counts": issue_counts,
        "notice": notice,
        "error": error,
        "status_labels": STATUS_LABELS,
        "severity_labels": SEVERITY_LABELS,
        "manifest_labels": MANIFEST_LABELS,
        **page(
            title="Vista previa de importación",
            section="vulnerabilities",
            case_id=case_id,
            case_title=case_title,
            crumbs=case_crumbs(
                case_id,
                case_title,
                Crumb("Vulnerabilidades", f"/cases/{case_id}/vulnerabilities"),
                Crumb("Vista previa"),
            ),
        ),
    }
    name = "vulnerabilities/_preview.html" if _is_htmx(request) else "vulnerabilities/preview.html"
    return _templates(request).TemplateResponse(
        request=request, name=name, context=context, status_code=status_code
    )


def _read_upload(upload: UploadFile, max_bytes: int) -> tuple[str, bytes]:
    filename = (upload.filename or "").replace("\\", "/").split("/")[-1].strip()
    if not filename:
        raise UploadRejected("validation_error", "Seleccioná un archivo CSV.", 422)
    if (
        Path(filename).suffix.lower() != ".csv"
        and (upload.content_type or "").lower() != "text/csv"
    ):
        raise UploadRejected("unsupported_media_type", "Solo se admite un archivo CSV.", 422)
    data = upload.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise UploadRejected(
            "payload_too_large",
            "El archivo supera el tamaño permitido.",
            413,
        )
    return filename, data


@router.get("/cases/{case_id}/vulnerabilities", response_class=HTMLResponse)
def vulnerabilities_view(request: Request, case_id: str):
    try:
        resolved_id, case_title = _case_header(request, case_id)
    except CaseNotFoundError:
        return _not_found(request)
    notice = NOTICES.get(request.query_params.get("notice", ""))
    try:
        return _render_section(
            request,
            resolved_id,
            case_title,
            import_id=request.query_params.get("import_id"),
            notice=notice,
        )
    except LookupError:
        return _not_found(request)


@router.get("/cases/{case_id}/vulnerabilities/imports", response_class=HTMLResponse)
def vulnerabilities_history_view(request: Request, case_id: str):
    try:
        resolved_id, case_title = _case_header(request, case_id)
    except CaseNotFoundError:
        return _not_found(request)
    with request.app.state.session_factory() as session:
        records = _history(session, resolved_id)
    context = {
        "case_id": resolved_id,
        "records": records,
        "status_labels": STATUS_LABELS,
        **page(
            title="Historial de importaciones",
            section="vulnerabilities",
            case_id=resolved_id,
            case_title=case_title,
            crumbs=case_crumbs(
                resolved_id,
                case_title,
                Crumb("Vulnerabilidades", f"/cases/{resolved_id}/vulnerabilities"),
                Crumb("Historial"),
            ),
        ),
    }
    return _templates(request).TemplateResponse(
        request=request, name="vulnerabilities/history.html", context=context
    )


@router.get("/cases/{case_id}/vulnerabilities/imports/new", response_class=HTMLResponse)
def vulnerabilities_form_view(request: Request, case_id: str):
    try:
        resolved_id, case_title = _case_header(request, case_id)
    except CaseNotFoundError:
        return _not_found(request)
    return _render_form(request, resolved_id, case_title)


@router.post("/cases/{case_id}/vulnerabilities/imports/validate", response_class=HTMLResponse)
def vulnerabilities_validate_view(
    request: Request,
    case_id: str,
    file: Annotated[UploadFile, File()],
):
    try:
        resolved_id, case_title = _case_header(request, case_id)
    except CaseNotFoundError:
        return _not_found(request)
    settings = request.app.state.settings
    try:
        filename, content = _read_upload(file, settings.qualys_max_bytes)
    except UploadRejected as exc:
        return _render_form(
            request,
            resolved_id,
            case_title,
            status_code=exc.status,
            errors={"file": exc.message},
        )

    service = QualysImportService(request.app.state.session_factory, settings)
    try:
        result = service.stage_import(resolved_id, filename, content)
    except CaseNotFoundError:
        return _not_found(request)

    if result.idempotent and result.import_record.status == "confirmed":
        target = f"/cases/{resolved_id}/vulnerabilities?notice=idempotent"
        if _is_htmx(request):
            return Response(status_code=200, headers={"HX-Redirect": target})
        return RedirectResponse(url=target, status_code=303)
    target = f"/cases/{resolved_id}/vulnerabilities/imports/{result.import_record.id}"
    if _is_htmx(request):
        return Response(status_code=200, headers={"HX-Redirect": target})
    return RedirectResponse(url=target, status_code=303)


@router.get(
    "/cases/{case_id}/vulnerabilities/imports/{import_id}",
    response_class=HTMLResponse,
)
def vulnerabilities_preview_view(request: Request, case_id: str, import_id: str):
    try:
        resolved_id, case_title = _case_header(request, case_id)
    except CaseNotFoundError:
        return _not_found(request)
    with request.app.state.session_factory() as session:
        record = _load_import(session, resolved_id, import_id)
    if record is None:
        return _not_found(request)
    return _render_preview(request, resolved_id, case_title, record)


@router.post(
    "/cases/{case_id}/vulnerabilities/imports/{import_id}/confirm",
    response_class=HTMLResponse,
)
def vulnerabilities_confirm_view(request: Request, case_id: str, import_id: str):
    try:
        resolved_id, case_title = _case_header(request, case_id)
    except CaseNotFoundError:
        return _not_found(request)
    service = QualysImportService(request.app.state.session_factory, request.app.state.settings)
    try:
        result = service.confirm_import(resolved_id, import_id)
    except ImportNotFoundError:
        return _not_found(request)
    except InvalidTransitionError as exc:
        status = 410 if exc.code == "import_expired" else 409
        with request.app.state.session_factory() as session:
            record = _load_import(session, resolved_id, import_id)
        if record is None:
            return _not_found(request)
        return _render_preview(
            request,
            resolved_id,
            case_title,
            record,
            status_code=status,
            error=exc.message,
        )
    notice_code = "idempotent" if result.idempotent else "confirmed"
    target = f"/cases/{resolved_id}/vulnerabilities?notice={notice_code}"
    if _is_htmx(request):
        return Response(status_code=200, headers={"HX-Redirect": target})
    return RedirectResponse(url=target, status_code=303)


@router.post(
    "/cases/{case_id}/vulnerabilities/imports/{import_id}/cancel",
    response_class=HTMLResponse,
)
def vulnerabilities_cancel_view(request: Request, case_id: str, import_id: str):
    try:
        resolved_id, case_title = _case_header(request, case_id)
    except CaseNotFoundError:
        return _not_found(request)
    service = QualysImportService(request.app.state.session_factory, request.app.state.settings)
    try:
        service.cancel_import(resolved_id, import_id)
    except ImportNotFoundError:
        return _not_found(request)
    except InvalidTransitionError as exc:
        with request.app.state.session_factory() as session:
            record = _load_import(session, resolved_id, import_id)
        if record is None:
            return _not_found(request)
        return _render_preview(
            request,
            resolved_id,
            case_title,
            record,
            status_code=409,
            error=exc.message,
        )
    target = f"/cases/{resolved_id}/vulnerabilities?notice=cancelled"
    if _is_htmx(request):
        return Response(status_code=200, headers={"HX-Redirect": target})
    return RedirectResponse(url=target, status_code=303)
