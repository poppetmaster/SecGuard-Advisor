"""Rutas de conversación documental, citas y evidencia de ejecución."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from secguard_advisor.cases.scope import (
    CaseNotFoundError,
    CaseScope,
    require_case,
    resolve_case_scope,
)
from secguard_advisor.conversation.concurrency import find_active_run
from secguard_advisor.conversation.retry import (
    RetryNotAllowed,
    RunNotFound,
    start_retry_turn,
)
from secguard_advisor.conversation.turn import execute_turn, start_question_turn
from secguard_advisor.conversation.views import conversation_view, run_view
from secguard_advisor.evidence.runs import ActiveRunConflict
from secguard_advisor.web.errors import message_for
from secguard_advisor.web.navigation import Crumb, case_crumbs, page

router = APIRouter(tags=["chat"])

MAX_QUESTION_CHARS = 2000


def _templates(request: Request):
    return request.app.state.templates


def _is_htmx(request: Request) -> bool:
    return request.headers.get("hx-request", "").lower() == "true"


def _resolve_scope(request: Request, case_id: str) -> CaseScope:
    with request.app.state.session_factory() as session:
        return resolve_case_scope(session, case_id)


def _panel_context(
    request: Request,
    case_id: str,
    *,
    errors: dict[str, str] | None = None,
    notice: str | None = None,
    failure: dict | None = None,
) -> dict:
    settings = request.app.state.settings
    with request.app.state.session_factory() as session:
        case = require_case(session, CaseScope(case_id=case_id))
        view = conversation_view(
            session,
            CaseScope(case_id=case_id),
            reviewer_configured=bool(settings.reviewer_name),
        )
        case_title = case.title
    return {
        "case_id": case_id,
        "errors": errors or {},
        "notice": notice,
        "failure": failure,
        **view,
        **page(
            title="Consulta documental",
            section="chat",
            case_id=case_id,
            case_title=case_title,
            crumbs=case_crumbs(case_id, case_title, Crumb("Consulta documental")),
        ),
    }


def _render(
    request: Request,
    case_id: str,
    *,
    status_code: int = 200,
    errors: dict[str, str] | None = None,
    notice: str | None = None,
    failure: dict | None = None,
    fragment: bool = True,
):
    context = _panel_context(
        request,
        case_id,
        errors=errors,
        notice=notice,
        failure=failure,
    )
    name = "chat/panel.html" if fragment and _is_htmx(request) else "chat/index.html"
    return _templates(request).TemplateResponse(
        request=request,
        name=name,
        context=context,
        status_code=status_code,
    )


def _not_found(request: Request):
    return _templates(request).TemplateResponse(
        request=request,
        name="errors/404.html",
        context={"message": "No encontrado en este caso."},
        status_code=404,
    )


def _run_generation(request: Request, scope: CaseScope, starter):
    """Adquiere el permiso global y ejecuta el turno, liberando siempre el permiso."""
    slot = request.app.state.generation_slot
    if not slot.acquire():
        return (
            429,
            {
                "notice": message_for("busy"),
                "failure": None,
            },
        )

    embedder = None
    try:
        embedder = request.app.state.embedder_factory()
        index = request.app.state.index_factory()
        generator = request.app.state.llm_factory()
        try:
            context = starter(generator, embedder, index)
        except ActiveRunConflict:
            return (
                409,
                {
                    "notice": message_for("conflict") + " El caso ya tiene una consulta en curso.",
                    "failure": None,
                },
            )

        result = execute_turn(context, memory=request.app.state.memory)
        if result.status == "succeeded":
            return 200, {"notice": None, "failure": None}
        message = message_for(result.error_code or "internal_error")
        return (
            result.http_status,
            {
                "notice": None,
                "failure": {"run_id": context.run_id, "message": message},
            },
        )
    finally:
        close = getattr(embedder, "close", None)
        if callable(close):
            close()
        slot.release()


@router.get("/cases/{case_id}/chat", response_class=HTMLResponse)
def chat_view(request: Request, case_id: str):
    try:
        _resolve_scope(request, case_id)
    except CaseNotFoundError:
        return _not_found(request)
    return _render(request, case_id)


@router.post("/cases/{case_id}/chat/messages", response_class=HTMLResponse)
def ask_view(
    request: Request,
    case_id: str,
    question: Annotated[str, Form()] = "",
):
    try:
        scope = _resolve_scope(request, case_id)
    except CaseNotFoundError:
        return _not_found(request)

    cleaned = (question or "").strip()
    if not cleaned:
        return _render(
            request,
            case_id,
            status_code=422,
            errors={"question": "Escribí una pregunta antes de enviar."},
        )
    if len(cleaned) > MAX_QUESTION_CHARS:
        return _render(
            request,
            case_id,
            status_code=422,
            errors={"question": "La pregunta supera los 2000 caracteres."},
        )

    with request.app.state.session_factory() as session:
        if find_active_run(session, scope.case_id) is not None:
            return _render(
                request,
                case_id,
                status_code=409,
                notice="El caso ya tiene una consulta en curso.",
            )

    def starter(generator, embedder, index):
        return start_question_turn(
            request.app.state.session_factory,
            request.app.state.settings,
            scope=scope,
            question=cleaned,
            generator=generator,
            embedder=embedder,
            index=index,
            token_counter=request.app.state.token_counter,
        )

    status_code, extras = _run_generation(request, scope, starter)
    return _render(request, case_id, status_code=status_code, **extras)


@router.post("/cases/{case_id}/runs/{run_id}/retry", response_class=HTMLResponse)
def retry_view(request: Request, case_id: str, run_id: str):
    try:
        scope = _resolve_scope(request, case_id)
    except CaseNotFoundError:
        return _not_found(request)

    def starter(generator, embedder, index):
        return start_retry_turn(
            request.app.state.session_factory,
            request.app.state.settings,
            scope=scope,
            run_id=run_id,
            generator=generator,
            embedder=embedder,
            index=index,
            token_counter=request.app.state.token_counter,
        )

    with request.app.state.session_factory() as session:
        if find_active_run(session, scope.case_id) is not None:
            return _render(
                request,
                case_id,
                status_code=409,
                notice="El caso ya tiene una consulta en curso.",
            )

    try:
        status_code, extras = _run_generation(request, scope, starter)
    except RunNotFound:
        return _not_found(request)
    except RetryNotAllowed as exc:
        return _render(request, case_id, status_code=409, notice=str(exc))

    if status_code == 200:
        status_code = 202
    return _render(request, case_id, status_code=status_code, **extras)


@router.get("/cases/{case_id}/runs/{run_id}", response_class=HTMLResponse)
def run_evidence_view(request: Request, case_id: str, run_id: str):
    try:
        scope = _resolve_scope(request, case_id)
    except CaseNotFoundError:
        return _not_found(request)

    with request.app.state.session_factory() as session:
        case = require_case(session, scope)
        view = run_view(session, scope, run_id)
        case_title = case.title
    if view is None:
        return _not_found(request)

    return _templates(request).TemplateResponse(
        request=request,
        name="chat/run.html",
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
