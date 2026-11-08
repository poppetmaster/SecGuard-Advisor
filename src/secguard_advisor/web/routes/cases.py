"""Rutas de creación, listado y consulta de casos."""

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from secguard_advisor.cases.schemas import CaseInput, CaseValidationError
from secguard_advisor.cases.scope import CaseNotFoundError, resolve_case_scope
from secguard_advisor.cases.service import (
    create_case,
    get_case,
    list_assets,
    list_cases,
)
from secguard_advisor.conversation.views import conversation_view
from secguard_advisor.db.transaction import unit_of_work
from secguard_advisor.documents.service import documents_overview

router = APIRouter(prefix="/cases", tags=["cases"])


def _templates(request: Request):
    return request.app.state.templates


def _is_htmx(request: Request) -> bool:
    return request.headers.get("hx-request", "").lower() == "true"


def _form_values(
    title: str,
    description: str,
    ai_application: str,
    data_processed: str,
    restrictions: str,
    assets: str,
) -> dict[str, str]:
    return {
        "title": title,
        "description": description,
        "ai_application": ai_application,
        "data_processed": data_processed,
        "restrictions": restrictions,
        "assets": assets,
    }


@router.get("", response_class=HTMLResponse)
def list_case_view(request: Request):
    with request.app.state.session_factory() as session:
        cases = list_cases(session)

    return _templates(request).TemplateResponse(
        request=request,
        name="cases/list.html",
        context={"cases": cases},
    )


@router.get("/new", response_class=HTMLResponse)
def new_case_view(request: Request):
    return _templates(request).TemplateResponse(
        request=request,
        name="cases/new.html",
        context={"values": {}, "errors": {}},
    )


@router.post("", response_class=HTMLResponse)
def create_case_view(
    request: Request,
    title: str = Form(""),
    description: str = Form(""),
    ai_application: str = Form(""),
    data_processed: str = Form(""),
    restrictions: str = Form(""),
    assets: str = Form(""),
):
    values = _form_values(title, description, ai_application, data_processed, restrictions, assets)

    try:
        data = CaseInput.from_form(
            title=title,
            description=description,
            ai_application=ai_application,
            data_processed=data_processed,
            restrictions=restrictions,
            assets=assets,
        )
    except CaseValidationError as exc:
        if _is_htmx(request):
            return _templates(request).TemplateResponse(
                request=request,
                name="cases/form.html",
                context={"values": values, "errors": exc.errors},
                status_code=422,
            )
        return _templates(request).TemplateResponse(
            request=request,
            name="cases/new.html",
            context={"values": values, "errors": exc.errors},
            status_code=422,
        )

    with unit_of_work(request.app.state.session_factory) as session:
        case = create_case(session, data)
        case_id = case.id

    target = f"/cases/{case_id}"
    if _is_htmx(request):
        return Response(status_code=303, headers={"HX-Redirect": target})
    return RedirectResponse(url=target, status_code=303)


@router.get("/{case_id}", response_class=HTMLResponse)
def detail_case_view(request: Request, case_id: str):
    try:
        with request.app.state.session_factory() as session:
            scope = resolve_case_scope(session, case_id)
            case = get_case(session, scope)
            assets = [asset.name for asset in list_assets(session, case.id)]
            documents = documents_overview(session, case.id)
            conversation = conversation_view(
                session,
                scope,
                reviewer_configured=bool(request.app.state.settings.reviewer_name),
            )
            view = {
                "id": case.id,
                "title": case.title,
                "description": case.description,
                "ai_application": case.ai_application,
                "data_processed": case.data_processed,
                "restrictions": case.restrictions,
                "created_at": case.created_at,
                "synthetic_notice": case.synthetic_notice,
                "assets": assets,
            }
    except CaseNotFoundError:
        return _templates(request).TemplateResponse(
            request=request,
            name="errors/404.html",
            context={"message": "No encontrado en este caso."},
            status_code=404,
        )

    return _templates(request).TemplateResponse(
        request=request,
        name="cases/detail.html",
        context={
            "case": view,
            "case_id": view["id"],
            "documents": documents,
            "errors": {},
            "chat": conversation,
        },
    )
