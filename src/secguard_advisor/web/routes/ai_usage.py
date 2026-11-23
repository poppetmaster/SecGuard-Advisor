"""Panel de uso y comparativos de IA (solo lectura)."""

from __future__ import annotations

from datetime import date
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from secguard_advisor.ai_usage.charts import (
    build_comparison_charts,
    build_consumption_charts,
)
from secguard_advisor.ai_usage.evaluations import build_comparison_view
from secguard_advisor.ai_usage.queries import (
    UsageFilterError,
    UsageFilters,
    build_usage_view,
)
from secguard_advisor.web.navigation import Crumb, page

router = APIRouter(tags=["settings"])


def _templates(request: Request):
    return request.app.state.templates


def _is_htmx(request: Request) -> bool:
    return request.headers.get("hx-request", "").lower() == "true"


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise UsageFilterError("La fecha indicada no es válida.") from exc


def _filters(request: Request) -> UsageFilters:
    query = request.query_params
    try:
        page_number = int(query.get("page") or 1)
    except ValueError:
        page_number = 1
    return UsageFilters(
        from_date=_parse_date(query.get("from")),
        to_date=_parse_date(query.get("to")),
        provider=query.get("provider") or None,
        model=query.get("model") or None,
        operation=query.get("operation") or None,
        status=query.get("status") or None,
        scope=query.get("scope") or "general",
        evaluation_id=query.get("evaluation_id") or None,
        page=max(1, page_number),
    )


def _url(filters: UsageFilters, *, tab: str, page_number: int | None = None) -> str:
    values: dict[str, str] = {"tab": tab}
    if filters.from_date:
        values["from"] = filters.from_date.isoformat()
    if filters.to_date:
        values["to"] = filters.to_date.isoformat()
    for key in ("provider", "model", "operation", "status"):
        value = getattr(filters, key)
        if value:
            values[key] = value
    if filters.scope and filters.scope != "general":
        values["scope"] = filters.scope
    if filters.evaluation_id:
        values["evaluation_id"] = filters.evaluation_id
    if page_number and page_number > 1:
        values["page"] = str(page_number)
    return f"/settings/ai/usage?{urlencode(values)}"


def _panel_context(
    request: Request,
    *,
    filters: UsageFilters,
    tab: str,
    error: str | None,
    evaluation_id: str | None,
    provider: str | None,
) -> dict:
    with request.app.state.session_factory() as session:
        usage = build_usage_view(session, filters)
        usage_charts = build_consumption_charts(usage)
        comparison = None
        if tab == "comparison":
            default_evaluation = (
                usage["options"]["evaluations"][0]["id"]
                if usage["options"]["evaluations"]
                else None
            )
            comparison = build_comparison_view(
                session,
                evaluation_id=evaluation_id or default_evaluation,
                provider=provider,
            )
            comparison_charts = build_comparison_charts(comparison)
    pages = usage["detail"]["pages"]
    usage["detail"]["prev_url"] = (
        _url(filters, tab="usage", page_number=usage["detail"]["page"] - 1)
        if usage["detail"]["page"] > 1
        else None
    )
    usage["detail"]["next_url"] = (
        _url(filters, tab="usage", page_number=usage["detail"]["page"] + 1)
        if usage["detail"]["page"] < pages
        else None
    )
    usage["urls"] = {
        "usage": _url(filters, tab="usage"),
        "comparison": _url(filters, tab="comparison"),
        "clear": "/settings/ai/usage",
    }
    if comparison is not None:
        comparison["urls"] = {
            "usage": _url(filters, tab="usage"),
            "comparison": _url(filters, tab="comparison"),
        }
    return {
        "usage": usage,
        "usage_charts": usage_charts,
        "comparison": comparison,
        "comparison_charts": comparison_charts if comparison is not None else None,
        "tab": tab,
        "error": error,
        "evaluation_id": evaluation_id,
        "provider_filter": provider,
        "wide": True,
        **page(
            title="Uso y comparativos de IA",
            section="ai_usage",
            crumbs=(Crumb("Uso y comparativos de IA"),),
        ),
    }


@router.get("/settings/ai/usage", response_class=HTMLResponse)
def view_usage(request: Request):
    tab = request.query_params.get("tab") or "usage"
    if tab not in {"usage", "comparison"}:
        tab = "usage"
    error = None
    try:
        filters = _filters(request)
        context = _panel_context(
            request,
            filters=filters,
            tab=tab,
            error=None,
            evaluation_id=request.query_params.get("evaluation_id"),
            provider=request.query_params.get("eval_provider") or None,
        )
    except UsageFilterError as exc:
        error = str(exc)
        context = _panel_context(
            request,
            filters=UsageFilters(),
            tab=tab,
            error=error,
            evaluation_id=None,
            provider=None,
        )
    name = "ai_usage/_panel.html" if _is_htmx(request) else "ai_usage/index.html"
    return _templates(request).TemplateResponse(
        request=request, name=name, context=context, status_code=200
    )
