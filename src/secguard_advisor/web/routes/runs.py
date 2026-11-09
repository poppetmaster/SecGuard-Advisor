"""Ruta de evidencia de ejecución, acotada al caso activo."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from secguard_advisor.cases.scope import (
    CaseNotFoundError,
    CaseScope,
    require_case,
    resolve_case_scope,
)
from secguard_advisor.conversation.views import run_view
from secguard_advisor.web.navigation import Crumb, case_crumbs, page

router = APIRouter(tags=["runs"])


def _templates(request: Request):
    return request.app.state.templates


def _resolve_scope(request: Request, case_id: str) -> CaseScope:
    with request.app.state.session_factory() as session:
        return resolve_case_scope(session, case_id)


def _not_found(request: Request):
    return _templates(request).TemplateResponse(
        request=request,
        name="errors/404.html",
        context={"message": "No encontrado en este caso."},
        status_code=404,
    )


@router.get("/cases/{case_id}/runs/{run_id}", response_class=HTMLResponse)
def run_evidence_view(request: Request, case_id: str, run_id: str):
    try:
        scope = _resolve_scope(request, case_id)
    except CaseNotFoundError:
        return _not_found(request)

    with request.app.state.session_factory() as session:
        case = require_case(session, scope)
        view = run_view(session, scope, run_id, factory=request.app.state.session_factory)
        case_title = case.title
    if view is None:
        return _not_found(request)

    return _templates(request).TemplateResponse(
        request=request,
        name="runs/show.html",
        context={
            "case_id": case_id,
            "run": view,
            **page(
                title="Evidencia de ejecución",
                section="chat",
                case_id=case_id,
                case_title=case_title,
                crumbs=case_crumbs(
                    case_id,
                    case_title,
                    Crumb("Consulta documental", f"/cases/{case_id}/chat"),
                    Crumb("Ejecución"),
                ),
            ),
        },
    )
