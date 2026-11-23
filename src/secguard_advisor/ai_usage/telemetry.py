"""Persistencia de telemetría por solicitud de modelo."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from secguard_advisor.conversation.llm import (
    InvalidModelOutput,
    ModelTimeout,
    ModelUnavailable,
)
from secguard_advisor.conversation.providers.base import (
    ProviderAuthError,
    ProviderError,
    ProviderRateLimited,
)
from secguard_advisor.conversation.providers.cost import TARIFF_VERSION, CostResult
from secguard_advisor.db.models import AiRequest, utc_now_iso

_EVALUATION_ID: ContextVar[str | None] = ContextVar("ai_usage_evaluation_id", default=None)
_SCENARIO: ContextVar[str | None] = ContextVar("ai_usage_scenario", default=None)


@contextmanager
def set_evaluation_context(evaluation_id: str | None, scenario: str | None):
    """Marca las solicitudes de una prueba comparativa sin tocar los prompts."""
    first = _EVALUATION_ID.set(evaluation_id)
    second = _SCENARIO.set(scenario)
    try:
        yield
    finally:
        _SCENARIO.reset(second)
        _EVALUATION_ID.reset(first)


def current_evaluation() -> tuple[str | None, str | None]:
    return _EVALUATION_ID.get(), _SCENARIO.get()


def _slug(value: str) -> str:
    return "".join(f"_{char.lower()}" if char.isupper() else char for char in value).lstrip("_")


def status_and_error(exc: BaseException) -> tuple[str, str]:
    """Traduce la excepción a un estado y código estables."""
    if isinstance(exc, ModelTimeout):
        return "timeout", "model_timeout"
    if isinstance(exc, ModelUnavailable):
        return "uncertain", "model_unavailable"
    if isinstance(exc, InvalidModelOutput):
        return "error", "invalid_model_output"
    if isinstance(exc, ProviderRateLimited):
        return "error", "provider_rate_limited"
    if isinstance(exc, ProviderAuthError):
        return "error", "provider_auth_error"
    if isinstance(exc, ProviderError):
        return "error", "provider_error"
    return "error", _slug(type(exc).__name__)


def _usage_source(usage: dict | None) -> str:
    source = (usage or {}).get("source")
    if source in {"observed", "estimated"}:
        return source
    return "unavailable"


def _token(usage: dict | None, *keys: str) -> int | None:
    values = usage or {}
    for key in keys:
        value = values.get(key)
        if value is not None:
            return int(value)
    return None


def _reasoning_included(usage: dict | None) -> bool | None:
    values = usage or {}
    if "reasoning_included_in_output" in values:
        return bool(values["reasoning_included_in_output"])
    return None


def record_ai_request(
    session: Session,
    *,
    run_id: str,
    operation: str,
    attempt_no: int,
    provider: str,
    model: str,
    started_at: str,
    duration_ms: int | None,
    usage: dict | None,
    cost: CostResult | None,
    status: str = "completed",
    error_code: str | None = None,
) -> AiRequest | None:
    """Registra un intento lógico una sola vez.

    La clave ``(run_id, operation, attempt_no)`` evita duplicados entre
    callbacks o una segunda observación del mismo intento.
    """
    existing = session.scalar(
        select(AiRequest).where(
            AiRequest.run_id == run_id,
            AiRequest.operation == operation,
            AiRequest.attempt_no == attempt_no,
        )
    )
    if existing is not None:
        return None
    if cost is None or provider == "ollama":
        cost_status = "not_applicable" if provider == "ollama" else "unknown"
        cost_usd: Decimal | None = None
        tariff_version = None
    else:
        cost_status = cost.status
        cost_usd = cost.usd
        tariff_version = cost.tariff_version
    evaluation_id, scenario = current_evaluation()
    row = AiRequest(
        run_id=run_id,
        operation=operation,
        attempt_no=attempt_no,
        provider=provider,
        model=model,
        started_at=started_at,
        finished_at=utc_now_iso(),
        status=status,
        duration_ms=duration_ms,
        input_tokens=_token(usage, "input_tokens", "prompt_tokens"),
        output_tokens=_token(usage, "output_tokens"),
        cached_tokens=_token(usage, "cached_tokens"),
        cache_write_tokens=_token(usage, "cache_write_tokens"),
        reasoning_tokens=_token(usage, "reasoning_tokens"),
        reasoning_included_in_output=_reasoning_included(usage),
        usage_source=_usage_source(usage),
        cost_usd=cost_usd,
        cost_status=cost_status,
        provider_reported_cost_usd=None,
        currency="USD",
        tariff_version=tariff_version,
        tariff_effective_at=TARIFF_VERSION if tariff_version else None,
        evaluation_id=evaluation_id,
        scenario=scenario,
        error_code=error_code,
    )
    session.add(row)
    return row
