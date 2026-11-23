"""Configuración de IA: selección de proveedor y parámetros no secretos."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from secguard_advisor.ai_config import (
    PROVIDER_LABELS,
    PROVIDERS,
    AIConfigurationError,
    load_view,
    save_configuration,
)
from secguard_advisor.ai_config.service import MODEL_CATALOG
from secguard_advisor.web.navigation import Crumb, page

router = APIRouter(tags=["settings"])


def _templates(request: Request):
    return request.app.state.templates


def _is_htmx(request: Request) -> bool:
    return request.headers.get("hx-request", "").lower() == "true"


def _context(request: Request, *, errors=None, notice=None, form=None) -> dict:
    with request.app.state.session_factory() as session:
        view = load_view(session, request.app.state.settings)
    settings = request.app.state.settings
    return {
        "view": view,
        "profiles": view.profiles,
        "providers": [
            {"id": provider, "label": PROVIDER_LABELS[provider]} for provider in PROVIDERS
        ],
        "model_catalog": MODEL_CATALOG,
        "run_timeout_seconds": settings.run_timeout_seconds,
        "errors": errors or {},
        "notice": notice,
        "form": form or {},
        **page(
            title="Configuración de IA",
            section="ai_settings",
            crumbs=(Crumb("Configuración de IA"),),
        ),
    }


def _render(
    request: Request, *, status_code=200, errors=None, notice=None, form=None, fragment=False
):
    context = _context(request, errors=errors, notice=notice, form=form)
    name = "ai_settings/_panel.html" if fragment and _is_htmx(request) else "ai_settings/index.html"
    return _templates(request).TemplateResponse(
        request=request, name=name, context=context, status_code=status_code
    )


@router.get("/settings/ai", response_class=HTMLResponse)
def view_settings(request: Request):
    return _render(request, fragment=False)


@router.get("/settings/ai/profile", response_class=HTMLResponse)
def view_profile(request: Request, provider: str):
    if provider not in PROVIDERS:
        return _render(
            request,
            status_code=422,
            errors={"provider": "Proveedor inválido."},
            form={"provider": provider},
            fragment=True,
        )
    context = _context(request)
    context["profile"] = context["view"].profiles[provider]
    context["selected_provider"] = provider
    return _templates(request).TemplateResponse(
        request=request,
        name="ai_settings/_fields.html",
        context=context,
        status_code=200,
    )


@router.post("/settings/ai", response_class=HTMLResponse)
def save_settings(
    request: Request,
    provider: Annotated[str, Form()] = "ollama",
    model: Annotated[str, Form()] = "",
    max_output_tokens: Annotated[str, Form()] = "",
    timeout_seconds: Annotated[str, Form()] = "",
):
    form = {
        "provider": provider,
        "model": model,
        "max_output_tokens": max_output_tokens,
        "timeout_seconds": timeout_seconds,
    }
    try:
        parsed_output = int(max_output_tokens)
        parsed_timeout = float(timeout_seconds)
    except TypeError, ValueError:
        return _render(
            request,
            status_code=422,
            errors={"form": "Revisá el máximo de tokens y el tiempo máximo por llamada."},
            form=form,
            fragment=True,
        )
    try:
        with request.app.state.session_factory() as session:
            save_configuration(
                session,
                request.app.state.settings,
                provider=provider,
                model=model,
                max_output_tokens=parsed_output,
                timeout_seconds=parsed_timeout,
            )
            session.commit()
    except AIConfigurationError as exc:
        return _render(
            request,
            status_code=422,
            errors={"form": str(exc)},
            form=form,
            fragment=True,
        )
    if not _is_htmx(request):
        return RedirectResponse(url="/settings/ai", status_code=303)
    return _render(
        request,
        notice="Configuración guardada. Las consultas nuevas usarán este perfil.",
        fragment=True,
    )
