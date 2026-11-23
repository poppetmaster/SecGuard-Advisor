"""Comparativo de evaluaciones importadas."""

from __future__ import annotations

import statistics
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select

from secguard_advisor.db.models import AiEvaluation, AiEvaluationResult, utc_now_iso

PROVIDER_ORDER = ("ollama", "deepseek", "anthropic")


def _decimal(value) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _order(provider: str) -> int:
    return PROVIDER_ORDER.index(provider) if provider in PROVIDER_ORDER else len(PROVIDER_ORDER)


def build_comparison_view(
    session,
    *,
    evaluation_id: str | None = None,
    provider: str | None = None,
) -> dict:
    evaluations = list(
        session.scalars(select(AiEvaluation).order_by(AiEvaluation.imported_at.desc()))
    )
    selected = None
    if evaluations:
        selected = next(
            (item for item in evaluations if item.id == evaluation_id),
            evaluations[0],
        )
    if selected is None:
        return {
            "evaluations": [],
            "evaluation": None,
            "providers": [],
            "scenarios": [],
            "common_scenarios": [],
            "common_executed": [],
            "missing": [],
            "notes": ["Todavía no hay evaluaciones importadas."],
            "provider_filter": provider,
        }
    statement = select(AiEvaluationResult).where(AiEvaluationResult.evaluation_id == selected.id)
    if provider:
        statement = statement.where(AiEvaluationResult.provider == provider)
    rows = list(session.scalars(statement.order_by(AiEvaluationResult.scenario)))
    groups: dict[tuple[str, str], list[AiEvaluationResult]] = defaultdict(list)
    for row in rows:
        groups[(row.provider, row.model)].append(row)
    providers = []
    for (name, model), items in sorted(groups.items(), key=lambda item: _order(item[0][0])):
        executed = [item for item in items if item.executed]
        durations = [item.duration_ms for item in executed if item.duration_ms is not None]
        cost_rows = [
            _decimal(item.cost_usd)
            for item in executed
            if item.cost_status == "calculated" and item.cost_usd is not None
        ]
        citation_emitted = sum(item.citations_emitted for item in executed)
        citation_valid = sum(item.citations_valid for item in executed)
        findings = [item for item in executed if item.findings_match is not None]
        abstention = [item for item in executed if item.abstention_ok is not None]
        quality = [
            _decimal(item.quality_score) for item in executed if item.quality_score is not None
        ]
        total_cost = sum(cost_rows, Decimal("0"))
        providers.append(
            {
                "provider": name,
                "model": model,
                "scenarios": {item.scenario for item in items},
                "executed": len(executed),
                "approved": sum(1 for item in items if item.result == "approved"),
                "successes": sum(1 for item in items if item.result == "approved"),
                "failed": sum(1 for item in items if item.result == "failed"),
                "blocked": sum(1 for item in items if item.result == "blocked"),
                "success_rate": round(
                    sum(1 for item in items if item.result == "approved") / len(executed), 4
                )
                if executed
                else None,
                "abstention_correct": sum(1 for item in abstention if item.abstention_ok is True),
                "abstention_runs": len(abstention),
                "tool_accuracy": round(
                    sum(1 for item in findings if item.findings_match) / len(findings),
                    4,
                )
                if findings
                else None,
                "tool_runs": len(findings),
                "citation_validity": round(citation_valid / citation_emitted, 4)
                if citation_emitted
                else None,
                "citations_emitted": citation_emitted,
                "citations_valid": citation_valid,
                "median_latency_ms": int(statistics.median(durations)) if durations else None,
                "input_tokens": sum(item.input_tokens or 0 for item in executed),
                "output_tokens": sum(item.output_tokens or 0 for item in executed),
                "cost_status": (
                    "calculated"
                    if any(item.cost_status == "calculated" for item in executed)
                    else (
                        "not_applicable"
                        if executed
                        and all(item.cost_status == "not_applicable" for item in executed)
                        else "unknown"
                    )
                ),
                "cost_total_usd": total_cost,
                "cost_per_scenario_usd": (total_cost / len(executed)).quantize(Decimal("0.000001"))
                if executed
                else None,
                "requests_label": "Histórico agregado",
                "quality_avg": round(float(sum(quality) / len(quality)), 2) if quality else None,
                "quality_method": next(
                    (item.quality_method for item in executed if item.quality_method),
                    None,
                ),
                "manual_review": "recorded"
                if any(item.manual_review == "recorded" for item in items)
                else "none",
                "detail_level": "aggregate"
                if all(item.detail_level == "aggregate" for item in items)
                else "mixed",
                "rows": {item.scenario: item for item in items},
            }
        )
    scenario_sets = [item["scenarios"] for item in providers]
    common = set.intersection(*scenario_sets) if scenario_sets else set()
    executed_sets = [
        {item.scenario for item in item.get("rows", {}).values() if item.executed}
        for item in providers
    ]
    common_executed = set.intersection(*executed_sets) if executed_sets else set()
    all_scenarios = set.union(*scenario_sets) if scenario_sets else set()
    missing = []
    for item in providers:
        absent = sorted(all_scenarios - item["scenarios"])
        if absent:
            missing.append(
                {
                    "provider": item["provider"],
                    "model": item["model"],
                    "scenarios": absent,
                }
            )
    matrix = []
    for scenario in sorted(common):
        matrix.append(
            {
                "scenario": scenario,
                "cells": [
                    {
                        "provider": item["provider"],
                        "model": item["model"],
                        "result": item["rows"][scenario].result
                        if scenario in item["rows"]
                        else None,
                        "outcome": item["rows"][scenario].outcome
                        if scenario in item["rows"]
                        else None,
                        "executed": item["rows"][scenario].executed
                        if scenario in item["rows"]
                        else False,
                    }
                    for item in providers
                ],
            }
        )
    notes = []
    if common_executed != common:
        notes.append(
            "La muestra común ejecutada es menor que la muestra común porque hay "
            "escenarios bloqueados o no ejecutados."
        )
    if any(item["detail_level"] == "aggregate" for item in providers):
        notes.append(
            "Los resultados importados son histórico agregado: no permiten reconstruir "
            "solicitudes individuales."
        )
    if any(item["manual_review"] == "none" for item in providers):
        notes.append("No hay revisión humana registrada para estos resultados.")
    return {
        "evaluations": [
            {
                "id": item.id,
                "name": item.name,
                "version": item.version,
                "frozen_at": item.frozen_at,
                "detail_level": item.detail_level,
            }
            for item in evaluations
        ],
        "evaluation": {
            "id": selected.id,
            "name": selected.name,
            "version": selected.version,
            "frozen_at": selected.frozen_at,
            "dataset_sha256": selected.dataset_sha256,
            "detail_level": selected.detail_level,
            "source": selected.source,
            "imported_at": selected.imported_at,
        },
        "providers": providers,
        "scenarios": sorted(all_scenarios),
        "common_scenarios": sorted(common),
        "common_executed": sorted(common_executed),
        "missing": missing,
        "matrix": matrix,
        "provider_filter": provider,
        "notes": notes,
        "generated_at": utc_now_iso(),
    }
