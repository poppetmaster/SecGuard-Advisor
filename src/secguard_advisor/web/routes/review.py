"""Ruta de revisión humana del respaldo semántico de una cita."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from secguard_advisor.cases.scope import (
    CaseNotFoundError,
    CaseScope,
    require_case,
    resolve_case_scope,
)
from secguard_advisor.conversation.views import citation_view, conversation_view
from secguard_advisor.db.models import Conversation, Message, MessageCitation
from secguard_advisor.retrieval.review import (
    CitationNotFound,
    ReviewNotAllowed,
    ReviewNotConfigured,
    review_citation,
)
from secguard_advisor.web.navigation import Crumb, case_crumbs, page

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


def _find_citation_view(
    session: Session,
    scope: CaseScope,
    message_id: str,
    citation_id: str,
) -> dict | None:
    message = session.get(Message, message_id)
    if message is None:
        return None
    conversation = session.get(Conversation, message.conversation_id)
    if conversation is None or conversation.case_id != scope.case_id:
        return None
    citation = session.scalar(
        select(MessageCitation).where(
            MessageCitation.id == citation_id,
            MessageCitation.message_id == message.id,
        )
    )
    if citation is None:
        return None
    return citation_view(session, scope.case_id, citation)


def _citation_response(
    request: Request,
    case_id: str,
    view: dict,
    *,
    status_code: int,
    error: str | None = None,
):
    return _templates(request).TemplateResponse(
        request=request,
        name="chat/_citation.html",
        context={
            "case_id": case_id,
            "citation": view,
            "reviewer_configured": bool(request.app.state.settings.reviewer_name),
            "error": error,
        },
        status_code=status_code,
    )


def _page(request: Request, case_id: str, *, notice: str | None, status_code: int):
    settings = request.app.state.settings
    with request.app.state.session_factory() as session:
        scope = resolve_case_scope(session, case_id)
        case = require_case(session, scope)
        view = conversation_view(
            session,
            scope,
            reviewer_configured=bool(settings.reviewer_name),
            factory=request.app.state.session_factory,
        )
        case_title = case.title
    return _templates(request).TemplateResponse(
        request=request,
        name="chat/index.html",
        context={
            "case_id": case_id,
            "errors": {},
            "notice": notice,
            "failure": None,
            **view,
            **page(
                title="Consulta documental",
                section="chat",
                case_id=case_id,
                case_title=case_title,
                crumbs=case_crumbs(case_id, case_title, Crumb("Consulta documental")),
            ),
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
        except CitationNotFound:
            session.rollback()
            return _not_found(request)
        except (ReviewNotConfigured, ReviewNotAllowed, ValueError) as exc:
            session.rollback()
            view = _find_citation_view(session, scope, message_id, citation_id)
            if view is None:
                return _not_found(request)
            return _citation_response(
                request,
                case_id,
                view,
                status_code=422 if isinstance(exc, ValueError) else 409,
                error=str(exc),
            )

    if not _is_htmx(request):
        return _page(request, case_id, notice="Revisión registrada.", status_code=200)

    return _citation_response(request, case_id, view, status_code=200)
