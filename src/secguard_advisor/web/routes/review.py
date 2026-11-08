"""Ruta de revisión humana del respaldo semántico de una cita."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from secguard_advisor.cases.scope import CaseNotFoundError, resolve_case_scope
from secguard_advisor.conversation.views import citation_view, conversation_view
from secguard_advisor.retrieval.review import (
    CitationNotFound,
    ReviewNotAllowed,
    ReviewNotConfigured,
    review_citation,
)

router = APIRouter(tags=["review"])


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


def _page(request: Request, case_id: str, *, notice: str | None, status_code: int):
    settings = request.app.state.settings
    with request.app.state.session_factory() as session:
        view = conversation_view(
            session,
            resolve_case_scope(session, case_id),
            reviewer_configured=bool(settings.reviewer_name),
        )
    return _templates(request).TemplateResponse(
        request=request,
        name="chat/index.html",
        context={
            "case_id": case_id,
            "errors": {},
            "notice": notice,
            "failure": None,
            **view,
        },
        status_code=status_code,
    )


@router.post(
    "/cases/{case_id}/messages/{message_id}/citations/{citation_id}/review",
    response_class=HTMLResponse,
)
def review_view(
    request: Request,
    case_id: str,
    message_id: str,
    citation_id: str,
    status: Annotated[str, Form()] = "",
    note: Annotated[str, Form()] = "",
):
    try:
        with request.app.state.session_factory() as session:
            scope = resolve_case_scope(session, case_id)
    except CaseNotFoundError:
        return _not_found(request)

    settings = request.app.state.settings
    with request.app.state.session_factory() as session:
        try:
            citation = review_citation(
                session,
                scope,
                message_id=message_id,
                citation_id=citation_id,
                status=status,
                note=note,
                reviewer_name=settings.reviewer_name,
            )
            session.commit()
            view = citation_view(session, case_id, citation)
        except ReviewNotConfigured as exc:
            session.rollback()
            return _page(request, case_id, notice=str(exc), status_code=409)
        except CitationNotFound:
            session.rollback()
            return _not_found(request)
        except ReviewNotAllowed as exc:
            session.rollback()
            return _page(request, case_id, notice=str(exc), status_code=409)
        except ValueError as exc:
            session.rollback()
            return _page(request, case_id, notice=str(exc), status_code=422)

    if not _is_htmx(request):
        return _page(request, case_id, notice="Revisión registrada.", status_code=200)

    return _templates(request).TemplateResponse(
        request=request,
        name="chat/_citation.html",
        context={
            "case_id": case_id,
            "citation": view,
            "reviewer_configured": True,
        },
        status_code=200,
    )
