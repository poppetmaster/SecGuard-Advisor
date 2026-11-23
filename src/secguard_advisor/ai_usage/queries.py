"""Consultas agregadas del panel de uso de IA."""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select

from secguard_advisor.db.models import (
    AiEvaluation,
    AiRequest,
    ProviderBudgetLedger,
    Run,
)

BOGOTA = ZoneInfo("America/Bogota")
OPERATIONS = ("decide", "generate", "repair", "remote_count")
REQUEST_STATUSES = ("completed", "error", "timeout", "uncertain")
SCOPES = ("general", "evaluation")
PROVIDER_ORDER = ("ollama", "deepseek", "anthropic")
PAGE_SIZE = 10
DEFAULT_DAYS = 7


class UsageFilterError(ValueError):
    """Filtros inválidos del panel."""


@dataclass(frozen=True, slots=True)
class UsageFilters:
    from_date: date | None = None
    to_date: date | None = None
    provider: str | None = None
    model: str | None = None
    operation: str | None = None
    status: str | None = None
    scope: str = "general"
    evaluation_id: str | None = None
    page: int = 1


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def resolve_period(filters: UsageFilters, *, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    today = now.astimezone(BOGOTA).date()
    to_date = filters.to_date or today
    from_date = filters.from_date or (to_date - timedelta(days=DEFAULT_DAYS - 1))
    if from_date > to_date:
        raise UsageFilterError("La fecha inicial no puede ser posterior a la fecha final.")
    start_local = datetime.combine(from_date, time.min, tzinfo=BOGOTA)
    end_local = datetime.combine(to_date + timedelta(days=1), time.min, tzinfo=BOGOTA)
    return {
        "from_date": from_date,
        "to_date": to_date,
        "from_local": from_date.isoformat(),
        "to_local": to_date.isoformat(),
        "from_utc": _iso(start_local),
        "to_utc_exclusive": _iso(end_local),
    }


def _validate(filters: UsageFilters) -> None:
    if filters.operation not in (None, *OPERATIONS):
        raise UsageFilterError("Tipo de operación inválido.")
    if filters.status not in (None, *REQUEST_STATUSES):
        raise UsageFilterError("Estado inválido.")
    if filters.scope not in SCOPES:
        raise UsageFilterError("Ámbito inválido.")
    if filters.scope == "evaluation" and filters.evaluation_id is None:
        raise UsageFilterError("Elegí una evaluación para el ámbito comparativo.")


def _decimal(value) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _sum_optional(values) -> int | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present)


def _run_metrics(run: Run, requests: list[AiRequest]) -> dict:
    detailed = bool(requests)
    if detailed:
        input_tokens = _sum_optional(item.input_tokens for item in requests)
        output_tokens = _sum_optional(item.output_tokens for item in requests)
        cached_tokens = _sum_optional(item.cached_tokens for item in requests)
        cost = sum(
            (
                _decimal(item.cost_usd) or Decimal("0")
                for item in requests
                if item.cost_status == "calculated"
            ),
            Decimal("0"),
        )
        cost_unknown = any(item.cost_status == "unknown" for item in requests)
        calculated_any = any(item.cost_status == "calculated" for item in requests)
        cost_display_status = (
            "calculated"
            if calculated_any
            else ("not_applicable" if run.generator_provider == "ollama" else "unknown")
        )
        external = sum(1 for item in requests if item.provider != "ollama")
        local = sum(1 for item in requests if item.provider == "ollama")
        coverage = {
            "observed": sum(1 for item in requests if item.usage_source == "observed"),
            "estimated": sum(1 for item in requests if item.usage_source == "estimated"),
            "unavailable": sum(1 for item in requests if item.usage_source == "unavailable"),
            "historical_runs": 0,
        }
        model_calls: int | None = len(requests)
        external_requests: int | None = external
        local_calls: int | None = local
    else:
        input_tokens = run.usage_input_tokens
        output_tokens = run.usage_output_tokens
        cached_tokens = run.usage_cached_tokens
        cost = _decimal(run.cost_usd) if run.cost_status == "calculated" else Decimal("0")
        cost_unknown = run.cost_status == "unknown"
        cost_display_status = run.cost_status
        coverage = {"observed": 0, "estimated": 0, "unavailable": 0, "historical_runs": 1}
        model_calls = None
        external_requests = None
        local_calls = None
    return {
        "run_id": run.id,
        "case_id": run.case_id,
        "provider": run.generator_provider,
        "model": run.generator_model,
        "status": run.status,
        "attempt_no": run.attempt_no,
        "retry_of_run_id": run.retry_of_run_id,
        "duration_ms": run.duration_ms,
        "started_at": run.started_at,
        "started_local": _local_label(run.started_at),
        "cost_usd": cost,
        "cost_status": cost_display_status,
        "cost_unknown": cost_unknown,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_tokens": cached_tokens,
        "model_calls": model_calls,
        "external_requests": external_requests,
        "local_calls": local_calls,
        "detailed": detailed,
        "coverage": coverage,
        "requests": requests,
    }


def _local_label(value: str | None) -> str | None:
    parsed = _parse_iso(value)
    if parsed is None:
        return None
    return parsed.astimezone(BOGOTA).strftime("%Y-%m-%d %H:%M")


def _request_view(row: AiRequest) -> dict:
    return {
        "id": row.id,
        "operation": row.operation,
        "status": row.status,
        "provider": row.provider,
        "model": row.model,
        "started_at": row.started_at,
        "started_local": _local_label(row.started_at),
        "duration_ms": row.duration_ms,
        "input_tokens": row.input_tokens,
        "output_tokens": row.output_tokens,
        "cached_tokens": row.cached_tokens,
        "reasoning_tokens": row.reasoning_tokens,
        "reasoning_included_in_output": row.reasoning_included_in_output,
        "usage_source": row.usage_source,
        "cost_status": row.cost_status,
        "cost_usd": _decimal(row.cost_usd),
        "currency": row.currency,
        "tariff_version": row.tariff_version,
        "evaluation_id": row.evaluation_id,
        "scenario": row.scenario,
        "error_code": row.error_code,
    }


def _provider_rows(runs: list[dict]) -> list[dict]:
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for run in runs:
        groups[(run["provider"], run["model"])].append(run)
    rows = []
    for (provider, model), items in groups.items():
        durations = [item["duration_ms"] for item in items if item["duration_ms"] is not None]
        cost = sum((item["cost_usd"] for item in items), Decimal("0"))
        detailed = [item for item in items if item["detailed"]]
        coverage = {
            "observed": sum(item["coverage"]["observed"] for item in items),
            "estimated": sum(item["coverage"]["estimated"] for item in items),
            "unavailable": sum(item["coverage"]["unavailable"] for item in items),
            "historical_runs": sum(item["coverage"]["historical_runs"] for item in items),
        }
        model_calls = sum(item["model_calls"] for item in detailed) if detailed else None
        external = sum(item["external_requests"] for item in detailed) if detailed else None
        local = sum(item["local_calls"] for item in detailed) if detailed else None
        queries = len(items)
        rows.append(
            {
                "provider": provider,
                "model": model,
                "queries": queries,
                "model_calls": model_calls,
                "external_requests": external,
                "local_calls": local,
                "successes": sum(1 for item in items if item["status"] == "succeeded"),
                "errors": sum(
                    1 for item in items if item["status"] in {"failed", "timeout", "interrupted"}
                ),
                "retries": sum(1 for item in items if item["attempt_no"] > 1),
                "input_tokens": _sum_optional(item["input_tokens"] for item in items),
                "output_tokens": _sum_optional(item["output_tokens"] for item in items),
                "cached_tokens": _sum_optional(item["cached_tokens"] for item in items),
                "median_latency_ms": int(statistics.median(durations)) if durations else None,
                "cost_usd": cost,
                "cost_status": (
                    "calculated"
                    if any(item["cost_status"] == "calculated" for item in items)
                    else (
                        "not_applicable"
                        if all(item["provider"] == "ollama" for item in items)
                        else "unknown"
                    )
                ),
                "avg_cost_per_query_usd": (cost / queries).quantize(Decimal("0.000001"))
                if queries
                else None,
                "coverage": coverage,
                "cost_unknown": any(item["cost_unknown"] for item in items),
                "incomplete": len(detailed) < len(items),
            }
        )
    return sorted(
        rows,
        key=lambda item: (
            PROVIDER_ORDER.index(item["provider"])
            if item["provider"] in PROVIDER_ORDER
            else len(PROVIDER_ORDER),
            item["model"],
        ),
    )


def _ledger_totals(session, run_ids: list[str]) -> tuple[Decimal, Decimal, int, int]:
    if not run_ids:
        return Decimal("0"), Decimal("0"), 0, 0
    rows = list(
        session.scalars(
            select(ProviderBudgetLedger).where(ProviderBudgetLedger.run_id.in_(run_ids))
        )
    )
    reserved = [row for row in rows if row.state == "reserved"]
    reconciled = [row for row in rows if row.state == "reconciled"]
    pending = sum((_decimal(row.reserved_usd) or Decimal("0") for row in reserved), Decimal("0"))
    uncertain = sum((_decimal(row.settled_usd) or Decimal("0") for row in reconciled), Decimal("0"))
    return pending, uncertain, len(reserved), len(reconciled)


def _charts(runs: list[dict], period: dict) -> dict:
    start = period["from_date"]
    end = period["to_date"]
    days = []
    cursor = start
    while cursor <= end:
        days.append(
            {
                "date": cursor.isoformat(),
                "label": cursor.strftime("%d/%m"),
                "cost": Decimal("0"),
                "input_tokens": 0,
                "output_tokens": 0,
                "series": defaultdict(int),
                "provider_data": defaultdict(
                    lambda: {
                        "requests": 0,
                        "input": 0,
                        "output": 0,
                        "cost": Decimal("0"),
                        "cost_records": 0,
                    }
                ),
            }
        )
        cursor += timedelta(days=1)
    index = {item["date"]: item for item in days}
    for run in runs:
        for request in run["requests"]:
            stamp = _parse_iso(request.started_at)
            local_date = stamp.astimezone(BOGOTA).date().isoformat() if stamp else None
            bucket = index.get(local_date)
            if bucket is None:
                continue
            provider_data = bucket["provider_data"][request.provider]
            provider_data["requests"] += 1
            provider_data["input"] += request.input_tokens or 0
            provider_data["output"] += request.output_tokens or 0
            if request.cost_status == "calculated":
                amount = _decimal(request.cost_usd) or Decimal("0")
                bucket["cost"] += amount
                provider_data["cost"] += amount
                provider_data["cost_records"] += 1
            bucket["input_tokens"] += request.input_tokens or 0
            bucket["output_tokens"] += request.output_tokens or 0
            bucket["series"][request.provider] += 1
        if run["detailed"]:
            continue
        stamp = _parse_iso(run["started_at"])
        local_date = stamp.astimezone(BOGOTA).date().isoformat() if stamp else None
        bucket = index.get(local_date)
        if bucket is None:
            continue
        provider_data = bucket["provider_data"][run["provider"]]
        provider_data["input"] += run["input_tokens"] or 0
        provider_data["output"] += run["output_tokens"] or 0
        bucket["cost"] += run["cost_usd"]
        bucket["input_tokens"] += run["input_tokens"] or 0
        bucket["output_tokens"] += run["output_tokens"] or 0
        if run["cost_status"] == "calculated":
            provider_data["cost"] += run["cost_usd"]
            provider_data["cost_records"] += 1
    providers = sorted(
        {provider for item in days for provider in item["series"]},
        key=lambda value: (
            PROVIDER_ORDER.index(value) if value in PROVIDER_ORDER else len(PROVIDER_ORDER)
        ),
    )
    max_cost = max((item["cost"] for item in days), default=Decimal("0"))
    max_requests = max(
        (sum(item["series"].get(provider, 0) for provider in providers) for item in days),
        default=0,
    )
    max_tokens = max(
        (max(item["input_tokens"], item["output_tokens"]) for item in days),
        default=0,
    )
    for item in days:
        item["cost_pct"] = float(item["cost"] / max_cost * 100) if max_cost else 0.0
        item["series_view"] = [
            {
                "provider": provider,
                "count": item["series"].get(provider, 0),
                "pct": (
                    item["series"].get(provider, 0) / max_requests * 100 if max_requests else 0.0
                ),
            }
            for provider in providers
        ]
        item["input_pct"] = item["input_tokens"] / max_tokens * 100 if max_tokens else 0.0
        item["output_pct"] = item["output_tokens"] / max_tokens * 100 if max_tokens else 0.0
        item["provider_data"] = dict(item["provider_data"])
    slot = max(1, len(providers)) * 12 + 8
    return {
        "days": days,
        "providers": providers,
        "width": max(320, len(days) * 30),
        "requests_width": max(320, len(days) * slot),
        "requests_slot": slot,
    }


def build_usage_view(
    session,
    filters: UsageFilters,
    *,
    now: datetime | None = None,
) -> dict:
    _validate(filters)
    period = resolve_period(filters, now=now)
    statement = select(Run).where(
        Run.started_at >= period["from_utc"],
        Run.started_at < period["to_utc_exclusive"],
    )
    if filters.provider:
        statement = statement.where(Run.generator_provider == filters.provider)
    if filters.model:
        statement = statement.where(Run.generator_model == filters.model)
    runs = list(session.scalars(statement.order_by(Run.started_at.desc())))
    run_ids = [run.id for run in runs]
    requests = (
        list(session.scalars(select(AiRequest).where(AiRequest.run_id.in_(run_ids))))
        if run_ids
        else []
    )
    if filters.scope == "evaluation":
        requests = [item for item in requests if item.evaluation_id is not None]
        if filters.evaluation_id:
            requests = [item for item in requests if item.evaluation_id == filters.evaluation_id]
    else:
        requests = [item for item in requests if item.evaluation_id is None]
    if filters.operation:
        requests = [item for item in requests if item.operation == filters.operation]
    if filters.status:
        requests = [item for item in requests if item.status == filters.status]
    if filters.operation or filters.status or filters.scope == "evaluation":
        matching = {item.run_id for item in requests}
        runs = [run for run in runs if run.id in matching]
        run_ids = [run.id for run in runs]
    grouped: dict[str, list[AiRequest]] = defaultdict(list)
    for item in requests:
        grouped[item.run_id].append(item)
    run_views = [
        _run_metrics(run, sorted(grouped.get(run.id, []), key=lambda item: item.started_at))
        for run in runs
    ]
    durations = [item["duration_ms"] for item in run_views if item["duration_ms"] is not None]
    coverage = {
        "observed": sum(item["coverage"]["observed"] for item in run_views),
        "estimated": sum(item["coverage"]["estimated"] for item in run_views),
        "unavailable": sum(item["coverage"]["unavailable"] for item in run_views),
        "historical_runs": sum(item["coverage"]["historical_runs"] for item in run_views),
    }
    pending, uncertain, pending_count, uncertain_count = _ledger_totals(session, run_ids)
    cards = {
        "queries": len(run_views),
        "external_requests": sum(item["external_requests"] or 0 for item in run_views),
        "local_calls": sum(item["local_calls"] or 0 for item in run_views),
        "input_tokens": _sum_optional(item["input_tokens"] for item in run_views),
        "output_tokens": _sum_optional(item["output_tokens"] for item in run_views),
        "cached_tokens": _sum_optional(item["cached_tokens"] for item in run_views),
        "cost_calculated_usd": sum((item["cost_usd"] for item in run_views), Decimal("0")),
        "calculated_queries": sum(1 for item in run_views if item["cost_status"] == "calculated"),
        "median_turn_latency_ms": int(statistics.median(durations)) if durations else None,
        "coverage": coverage,
        "pending_reservations_usd": pending,
        "pending_reservations_count": pending_count,
        "uncertain_committed_usd": uncertain,
        "uncertain_committed_count": uncertain_count,
        "unknown_cost_runs": sum(1 for item in run_views if item["cost_unknown"]),
    }
    charts = _charts(run_views, period)
    pages = max(1, (len(run_views) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(max(1, filters.page), pages)
    detail = run_views[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]
    for item in detail:
        item["requests"] = [_request_view(row) for row in item["requests"]]
    all_runs = list(session.scalars(select(Run)))
    evaluations = list(
        session.scalars(select(AiEvaluation).order_by(AiEvaluation.imported_at.desc()))
    )
    return {
        "period": period,
        "cards": cards,
        "charts": charts,
        "providers": _provider_rows(run_views),
        "detail": {
            "entries": detail,
            "page": page,
            "pages": pages,
            "total": len(run_views),
            "page_size": PAGE_SIZE,
        },
        "filters": filters,
        "options": {
            "providers": sorted(
                {run.generator_provider for run in all_runs},
                key=lambda value: (
                    PROVIDER_ORDER.index(value) if value in PROVIDER_ORDER else len(PROVIDER_ORDER)
                ),
            ),
            "models": sorted({run.generator_model for run in all_runs}),
            "operations": OPERATIONS,
            "statuses": REQUEST_STATUSES,
            "evaluations": [
                {"id": item.id, "name": item.name, "version": item.version} for item in evaluations
            ],
        },
        "states": {
            "no_data": not run_views,
            "no_requests": not requests,
            "historical_only": bool(run_views) and not requests,
        },
    }
