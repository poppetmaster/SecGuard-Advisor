"""Registro de uso, costo y presupuesto alrededor de cada llamada al modelo."""

from __future__ import annotations

import time
from contextlib import contextmanager
from decimal import Decimal

from secguard_advisor.ai_usage.telemetry import record_ai_request, status_and_error
from secguard_advisor.conversation.llm import elapsed_ms
from secguard_advisor.conversation.providers.cost import TARIFF_VERSION, CostResult
from secguard_advisor.db.models import ProviderUsage, Run, utc_now_iso
from secguard_advisor.evidence.budget import begin_call, reconcile_call, settle_call


def _usage_value(usage: dict, *keys: str) -> int | None:
    for key in keys:
        value = usage.get(key)
        if value is not None:
            return int(value)
    return None


def _update_run(session, run_id: str, provider: str, usage: dict, cost: CostResult) -> None:
    run = session.get(Run, run_id)
    if run is None:
        return
    input_tokens = _usage_value(usage, "input_tokens", "prompt_tokens")
    output_tokens = _usage_value(usage, "output_tokens")
    cached_tokens = _usage_value(usage, "cached_tokens")
    cache_write_tokens = _usage_value(usage, "cache_write_tokens")
    if input_tokens is not None:
        run.usage_input_tokens = (run.usage_input_tokens or 0) + input_tokens
    if output_tokens is not None:
        run.usage_output_tokens = (run.usage_output_tokens or 0) + output_tokens
    if cached_tokens is not None:
        run.usage_cached_tokens = (run.usage_cached_tokens or 0) + cached_tokens
    if cache_write_tokens is not None:
        run.usage_cache_write_tokens = (run.usage_cache_write_tokens or 0) + cache_write_tokens
    run.usage_source = usage.get("source") or run.usage_source or "unknown"
    if provider == "ollama":
        run.cost_status = "not_applicable"
        run.cost_usd = None
        return
    if cost.status == "calculated" and cost.usd is not None:
        if run.cost_status != "unknown":
            run.cost_usd = (run.cost_usd or Decimal("0")) + cost.usd
            run.cost_status = "calculated"
            run.cost_tariff_version = cost.tariff_version
    else:
        run.cost_status = "unknown"
        run.cost_usd = None


@contextmanager
def provider_call(context, *, operation: str, admitted_tokens: int):
    """Reserva antes de la llamada y liquida/registra después.

    Un error de envío incierto conserva la reserva comprometida. No se libera
    como gasto cero.
    """
    settings = context.deps.settings
    generator = context.deps.generator
    provider = getattr(generator, "provider", settings.generation_provider)
    model = getattr(generator, "model", settings.provider_model)
    reservation = None
    if provider != "ollama":
        with context.factory() as session:
            reservation = begin_call(
                session,
                settings=settings,
                run_id=context.run_id,
                attempt_no=context.attempt_no,
                provider=provider,
                model=model,
                input_tokens=max(1, admitted_tokens),
                max_output_tokens=settings.provider_max_output_tokens,
            )
            session.commit()
    started_at = utc_now_iso()
    started = time.perf_counter()
    try:
        yield
    except Exception as exc:
        duration = elapsed_ms(started)
        usage = getattr(generator, "last_usage", None) or {}
        status, error_code = status_and_error(exc)
        input_tokens = _usage_value(usage, "input_tokens", "prompt_tokens")
        output_tokens = _usage_value(usage, "output_tokens")
        cost = (
            CostResult("not_applicable", None, None, {"reason": "local"})
            if provider == "ollama"
            else CostResult("unknown", None, None, {"reason": "call_failed"})
        )
        with context.factory() as session:
            if reservation is not None:
                if input_tokens is not None and output_tokens is not None:
                    cost = settle_call(
                        session,
                        reservation,
                        provider=provider,
                        model=model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cached_tokens=_usage_value(usage, "cached_tokens"),
                        cache_write_tokens=_usage_value(usage, "cache_write_tokens"),
                        tariff_version=settings.external_tariff_version,
                    )
                else:
                    reconcile_call(session, reservation)
                session.add(
                    ProviderUsage(
                        run_id=context.run_id,
                        attempt_no=context.attempt_no,
                        operation=operation,
                        provider=provider,
                        model=model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cached_tokens=_usage_value(usage, "cached_tokens"),
                        cache_write_tokens=_usage_value(usage, "cache_write_tokens"),
                        usage_source=usage.get("source") or "unknown",
                        duration_ms=duration,
                        cost_usd=cost.usd,
                        cost_status=cost.status,
                        tariff_version=cost.tariff_version or settings.external_tariff_version,
                    )
                )
            if usage or reservation is not None:
                _update_run(session, context.run_id, provider, usage, cost)
            record_ai_request(
                session,
                run_id=context.run_id,
                operation=operation,
                attempt_no=context.attempt_no,
                provider=provider,
                model=model,
                started_at=started_at,
                duration_ms=duration,
                usage=usage,
                cost=cost,
                status=status,
                error_code=error_code,
            )
            session.commit()
        raise
    duration = elapsed_ms(started)
    usage = getattr(generator, "last_usage", None) or {}
    cost = CostResult("not_applicable", None, None, {"reason": "local"})
    with context.factory() as session:
        if reservation is not None:
            cost = settle_call(
                session,
                reservation,
                provider=provider,
                model=model,
                input_tokens=_usage_value(usage, "input_tokens", "prompt_tokens"),
                output_tokens=_usage_value(usage, "output_tokens"),
                cached_tokens=_usage_value(usage, "cached_tokens"),
                cache_write_tokens=_usage_value(usage, "cache_write_tokens"),
                tariff_version=settings.external_tariff_version,
            )
            session.add(
                ProviderUsage(
                    run_id=context.run_id,
                    attempt_no=context.attempt_no,
                    operation=operation,
                    provider=provider,
                    model=model,
                    input_tokens=_usage_value(usage, "input_tokens", "prompt_tokens"),
                    output_tokens=_usage_value(usage, "output_tokens"),
                    cached_tokens=_usage_value(usage, "cached_tokens"),
                    cache_write_tokens=_usage_value(usage, "cache_write_tokens"),
                    usage_source=usage.get("source") or "observed",
                    duration_ms=duration,
                    cost_usd=cost.usd,
                    cost_status=cost.status,
                    tariff_version=cost.tariff_version or TARIFF_VERSION,
                    created_at=utc_now_iso(),
                )
            )
        record_ai_request(
            session,
            run_id=context.run_id,
            operation=operation,
            attempt_no=context.attempt_no,
            provider=provider,
            model=model,
            started_at=started_at,
            duration_ms=duration,
            usage=usage,
            cost=cost,
            status="completed",
        )
        _update_run(session, context.run_id, provider, usage, cost)
        session.commit()
