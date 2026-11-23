"""Manual report notification routes."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from secguard_advisor.cases.scope import CaseNotFoundError, require_case, resolve_case_scope
from secguard_advisor.notifications.channels.telegram import build_transport
from secguard_advisor.notifications.confirmations import (
    create_confirmation,
    get_confirmation,
    validate_confirmation,
)
from secguard_advisor.notifications.contacts import eligible_contacts, mask_chat_id
from secguard_advisor.notifications.delivery import event_view, get_event, list_events
from secguard_advisor.notifications.errors import NotificationError
from secguard_advisor.notifications.manual import retry_manual, send_manual
from secguard_advisor.reports.canonical import parse_json
from secguard_advisor.reports.errors import ReportError
from secguard_advisor.reports.service import get_version
from secguard_advisor.web.navigation import Crumb, case_crumbs, page

router = APIRouter(tags=["notifications"])


def _templates(request: Request):
    return request.app.state.templates


def _transport(request: Request):
    if request.app.state.telegram_transport is None:
        request.app.state.telegram_transport = build_transport(request.app.state.settings)
    return request.app.state.telegram_transport


def _case(request: Request, case_id: str):
    with request.app.state.session_factory() as session:
        scope = resolve_case_scope(session, case_id)
        case = require_case(session, scope)
        return case.id, case.title


def _not_found(request: Request):
    return _templates(request).TemplateResponse(
        request=request,
        name="errors/404.html",
        context={"message": "No encontrado."},
        status_code=404,
    )


def _preview_context(
    session,
    request: Request,
    case_id: str,
    report_id: str,
    version_number: int,
    *,
    confirmation_id: str | None = None,
    error: str | None = None,
):
    case_id, case_title = _case(request, case_id)
    version = get_version(session, case_id, report_id, version_number)
    contacts = eligible_contacts(session, case_id)
    confirmation = None
    manifest = None
    if confirmation_id:
        confirmation = get_confirmation(session, case_id, confirmation_id)
        try:
            _, manifest, _ = validate_confirmation(session, confirmation)
        except NotificationError as exc:
            error = exc.message
    return {
        "case_id": case_id,
        "case_title": case_title,
        "report_id": report_id,
        "version": version,
        "contacts": [
            {"id": item.id, "alias": item.alias, "masked_chat": mask_chat_id(item.chat_id)}
            for item in contacts
        ],
        "manifest": manifest or parse_json(confirmation.manifest_json) if confirmation else None,
        "confirmation": confirmation,
        "error": error,
        "events": [
            event_view(session, event)
            for event in list_events(session, case_id)
            if event.report_version_id == version.id
        ],
    }


@router.get(
    "/cases/{case_id}/reports/{report_id}/versions/{version_number}/notifications",
    response_class=HTMLResponse,
)
def notifications_preview(
    request: Request,
    case_id: str,
    report_id: str,
    version_number: int,
    confirmation_id: str | None = None,
):
    try:
        with request.app.state.session_factory() as session:
            context = _preview_context(
                session,
                request,
                case_id,
                report_id,
                version_number,
                confirmation_id=confirmation_id,
            )
    except CaseNotFoundError, NotificationError:
        return _not_found(request)
    return _templates(request).TemplateResponse(
        request=request,
        name="notifications/preview.html",
        context={
            **context,
            "wide": True,
            **page(
                title="Envío manual",
                section="reports",
                case_id=context["case_id"],
                case_title=context["case_title"],
                crumbs=case_crumbs(
                    context["case_id"],
                    context["case_title"],
                    Crumb("Informe ejecutivo", f"/cases/{context['case_id']}/reports"),
                    Crumb(f"Versión {version_number}"),
                    Crumb("Envío manual"),
                ),
            ),
        },
    )


@router.post(
    "/cases/{case_id}/reports/{report_id}/versions/{version_number}/confirmations",
    response_class=HTMLResponse,
)
def notifications_confirm(
    request: Request,
    case_id: str,
    report_id: str,
    version_number: int,
    contact_ids: list[str] = Form([]),  # noqa: B008
    created_by: str = Form(""),
):
    try:
        with request.app.state.session_factory() as session:
            confirmation = create_confirmation(
                session,
                case_id=case_id,
                report_id=report_id,
                version_number=version_number,
                contact_ids=contact_ids,
                created_by=created_by,
            )
            session.commit()
            confirmation_id = confirmation.id
    except (CaseNotFoundError, NotificationError, ReportError) as exc:
        with request.app.state.session_factory() as session:
            context = _preview_context(
                session,
                request,
                case_id,
                report_id,
                version_number,
                error=getattr(exc, "message", "No encontrado."),
            )
        return _templates(request).TemplateResponse(
            request=request,
            name="notifications/preview.html",
            context={
                **context,
                "wide": True,
                **page(
                    title="Envío manual",
                    section="reports",
                    case_id=context["case_id"],
                    case_title=context["case_title"],
                ),
            },
            status_code=422,
        )
    return RedirectResponse(
        f"/cases/{case_id}/reports/{report_id}/versions/{version_number}/notifications?confirmation_id={confirmation_id}",
        status_code=303,
    )


@router.post(
    "/cases/{case_id}/reports/{report_id}/versions/{version_number}/notifications",
    response_class=HTMLResponse,
)
def notifications_send(
    request: Request,
    case_id: str,
    report_id: str,
    version_number: int,
    confirmation_id: str = Form(""),
):
    try:
        send_manual(
            request.app.state.session_factory,
            request.app.state.settings,
            _transport(request),
            case_id=case_id,
            confirmation_id=confirmation_id,
        )
    except (CaseNotFoundError, NotificationError, ReportError) as exc:
        with request.app.state.session_factory() as session:
            context = _preview_context(
                session,
                request,
                case_id,
                report_id,
                version_number,
                confirmation_id=confirmation_id,
                error=getattr(exc, "message", "No se pudo enviar."),
            )
        return _templates(request).TemplateResponse(
            request=request,
            name="notifications/preview.html",
            context={
                **context,
                "wide": True,
                **page(
                    title="Envío manual",
                    section="reports",
                    case_id=context["case_id"],
                    case_title=context["case_title"],
                ),
            },
            status_code=409 if getattr(exc, "code", "") == "manifest_mismatch" else 422,
        )
    return RedirectResponse(f"/cases/{case_id}/notifications", status_code=303)


@router.get("/cases/{case_id}/notifications", response_class=HTMLResponse)
def notifications_history(request: Request, case_id: str):
    try:
        case_id, case_title = _case(request, case_id)
    except CaseNotFoundError:
        return _not_found(request)
    with request.app.state.session_factory() as session:
        events = [event_view(session, event) for event in list_events(session, case_id)]
    return _templates(request).TemplateResponse(
        request=request,
        name="notifications/history.html",
        context={
            "case_id": case_id,
            "events": events,
            "wide": True,
            **page(
                title="Informes y notificaciones",
                section="reports",
                case_id=case_id,
                case_title=case_title,
                crumbs=case_crumbs(case_id, case_title, Crumb("Informes y notificaciones")),
            ),
        },
    )


@router.post("/cases/{case_id}/notifications/{event_id}/retry", response_class=HTMLResponse)
def notifications_retry(request: Request, case_id: str, event_id: str):
    try:
        _case(request, case_id)
        with request.app.state.session_factory() as session:
            get_event(session, case_id, event_id)
        retry_manual(
            request.app.state.session_factory,
            request.app.state.settings,
            _transport(request),
            case_id=case_id,
            event_id=event_id,
        )
    except (CaseNotFoundError, NotificationError, ReportError) as exc:
        return _templates(request).TemplateResponse(
            request=request,
            name="errors/404.html",
            context={"message": getattr(exc, "message", "No se pudo reintentar.")},
            status_code=409,
        )
    return RedirectResponse(f"/cases/{case_id}/notifications", status_code=303)
