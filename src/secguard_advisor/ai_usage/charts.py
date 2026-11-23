"""Datos serializables para las gráficas ECharts del panel de uso."""

from __future__ import annotations

from decimal import Decimal

PROVIDER_META = {
    "ollama": {"name": "Ollama (local)", "color": "#2563eb"},
    "deepseek": {"name": "DeepSeek (API)", "color": "#7c3aed"},
    "anthropic": {"name": "Claude (API)", "color": "#ea580c"},
}
RESULT_META = {
    "approved": {"name": "Aprobado", "color": "#16a34a"},
    "failed": {"name": "Fallido", "color": "#dc2626"},
    "blocked": {"name": "Bloqueado", "color": "#d97706"},
}


def _provider(key: str) -> dict:
    return PROVIDER_META.get(key, {"name": key, "color": "#475569"})


def _number(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _cost_or_none(provider_data: dict, key: str) -> dict | None:
    data = provider_data.get(key)
    if not data or not data.get("cost_records"):
        return None
    return {
        "value": _number(data["cost"]),
        "coverage": (
            "1 registro con costo conocido"
            if data["cost_records"] == 1
            else f"{data['cost_records']} registros con costo conocido"
        ),
    }


def build_consumption_charts(usage: dict) -> dict:
    days = usage["charts"]["days"]
    labels = [day["label"] for day in days]
    dates = [day["date"] for day in days]
    providers = [
        provider
        for provider in ("ollama", "deepseek", "anthropic")
        if any(provider in day["provider_data"] for day in days)
    ]
    cost_series = []
    for provider in providers:
        if provider == "ollama":
            continue
        values = [_cost_or_none(day["provider_data"], provider) for day in days]
        if any(value is not None for value in values):
            meta = _provider(provider)
            cost_series.append(
                {"key": provider, "name": meta["name"], "color": meta["color"], "data": values}
            )
    request_series = []
    for provider in providers:
        meta = _provider(provider)
        values = [day["provider_data"].get(provider, {}).get("requests", 0) for day in days]
        if any(values):
            request_series.append(
                {"key": provider, "name": meta["name"], "color": meta["color"], "data": values}
            )
    token_series = []
    for provider in providers:
        meta = _provider(provider)
        input_total = sum(day["provider_data"].get(provider, {}).get("input", 0) for day in days)
        output_total = sum(day["provider_data"].get(provider, {}).get("output", 0) for day in days)
        if input_total or output_total:
            token_series.append(
                {
                    "key": provider,
                    "name": meta["name"],
                    "color": meta["color"],
                    "input": input_total,
                    "output": output_total,
                }
            )
    return {
        "labels": labels,
        "dates": dates,
        "providers": providers,
        "cost": {"series": cost_series, "unit": "USD", "labels": labels, "dates": dates},
        "requests": {
            "series": request_series,
            "unit": "intentos",
            "labels": labels,
            "dates": dates,
        },
        "tokens": {"providers": token_series, "unit": "tokens"},
        "notes": {
            "cost": (
                "Solo costo conocido por API. Ollama no tiene cobro por API. "
                "Los días sin costo conocido no se dibujan como cero."
            ),
            "requests": "Incluye solicitudes API externas y llamadas locales a Ollama.",
            "tokens": "Entrada y salida no suman caché de nuevo. No se imputan valores ausentes.",
        },
    }


def build_comparison_charts(comparison: dict) -> dict:
    providers = comparison["providers"]
    latency = []
    results = []
    cost = []
    for item in providers:
        meta = _provider(item["provider"])
        functional = item["functional"]
        if functional["median_latency_ms"] is not None:
            latency.append(
                {
                    "key": item["provider"],
                    "name": meta["name"],
                    "seconds": round(functional["median_latency_ms"] / 1000, 3),
                    "coverage": f"n={functional['latency_denominator']}",
                }
            )
        results.append(
            {
                "key": item["provider"],
                "name": meta["name"],
                "approved": item["approved"],
                "failed": item["failed"],
                "blocked": item["blocked"],
            }
        )
        if item["provider"] != "ollama" and functional["known_cost_records"]:
            cost.append(
                {
                    "key": item["provider"],
                    "name": meta["name"],
                    "value": _number(functional["cost_per_scenario_usd"]),
                    "coverage": (
                        f"{functional['known_cost_records']}/"
                        f"{functional['cost_denominator']} escenarios con costo conocido"
                    ),
                    "unknown": functional["unknown_cost_records"],
                }
            )
    provider_keys = [item["provider"] for item in providers]
    scenarios = comparison["common_scenarios"]
    cells = []
    for scenario_index, scenario in enumerate(scenarios):
        row = next((item for item in comparison["matrix"] if item["scenario"] == scenario), None)
        if row is None:
            continue
        for provider_index, provider_key in enumerate(provider_keys):
            cell = next((item for item in row["cells"] if item["provider"] == provider_key), None)
            if cell is None:
                continue
            cells.append(
                {
                    "provider_index": provider_index,
                    "scenario_index": scenario_index,
                    "provider": provider_key,
                    "scenario": scenario,
                    "result": cell["result"] or "failed",
                    "duration_ms": cell["duration_ms"],
                    "model": cell["model"],
                }
            )
    return {
        "latency": latency,
        "results": results,
        "cost": cost,
        "matrix": {
            "providers": [item["provider"] for item in providers],
            "provider_names": [_provider(item["provider"])["name"] for item in providers],
            "scenarios": scenarios,
            "cells": cells,
        },
        "quality": {
            "available": False,
            "message": (
                "No hay puntuaciones por dimensión registradas. No se derivan dimensiones "
                "a partir del promedio."
            ),
        },
        "result_meta": RESULT_META,
    }
