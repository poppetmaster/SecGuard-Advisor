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
    scenario_sets = [{item.scenario for item in items} for items in groups.values()]
    common = set.intersection(*scenario_sets) if scenario_sets else set()
    executed_sets = [
        {item.scenario for item in items if item.executed} for items in groups.values()
    ]
    common_executed = set.intersection(*executed_sets) if executed_sets else set()
    providers = []
    for (name, model), items in sorted(groups.items(), key=lambda item: _order(item[0][0])):
        executed = [item for item in items if item.executed]
        functional_rows = [item for item in executed if item.scenario in common_executed]
        durations = [item.duration_ms for item in functional_rows if item.duration_ms is not None]
        cost_rows = [
            _decimal(item.cost_usd)
            for item in items
            if item.cost_status == "calculated" and item.cost_usd is not None
        ]
        unknown_cost = [item for item in items if item.cost_status == "unknown"]
        not_applicable = [item for item in items if item.cost_status == "not_applicable"]
        citation_emitted = sum(item.citations_emitted for item in functional_rows)
        citation_valid = sum(item.citations_valid for item in functional_rows)
        findings = [item for item in functional_rows if item.findings_match is not None]
        abstention = [item for item in functional_rows if item.abstention_ok is not None]
        quality = [
            _decimal(item.quality_score)
            for item in functional_rows
            if item.quality_score is not None
        ]
        functional_cost_rows = [
            _decimal(item.cost_usd)
            for item in functional_rows
            if item.cost_status == "calculated" and item.cost_usd is not None
        ]
        functional_unknown = [item for item in functional_rows if item.cost_status == "unknown"]
        functional_cost = sum(functional_cost_rows, Decimal("0"))
        functional_cost_denominator = len(functional_cost_rows) + len(functional_unknown)
        total_cost = sum(cost_rows, Decimal("0"))
        cost_denominator = len(cost_rows) + len(unknown_cost)
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
                    sum(1 for item in functional_rows if item.result == "approved")
                    / len(functional_rows),
                    4,
                )
                if functional_rows
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
                "input_tokens": sum(item.input_tokens or 0 for item in functional_rows),
                "output_tokens": sum(item.output_tokens or 0 for item in functional_rows),
                "cost_status": (
                    "calculated"
                    if cost_rows
                    else (
                        "not_applicable"
                        if not_applicable and not unknown_cost and not cost_rows
                        else "unknown"
                    )
                ),
                "cost_total_usd": total_cost,
                "cost_per_scenario_usd": (total_cost / len(items)).quantize(Decimal("0.000001"))
                if items
                else None,
                "requests_label": "Histórico agregado",
                "quality_avg": round(float(sum(quality) / len(quality)), 2) if quality else None,
                "quality_method": next(
                    (item.quality_method for item in functional_rows if item.quality_method),
                    None,
                ),
                "manual_review": "recorded"
                if any(item.manual_review == "recorded" for item in items)
                else "none",
                "detail_level": "aggregate"
                if all(item.detail_level == "aggregate" for item in items)
                else "mixed",
                "consumption": {
                    "records": len(items),
                    "blocked": sum(1 for item in items if not item.executed),
                    "input_tokens": sum(item.input_tokens or 0 for item in items),
                    "output_tokens": sum(item.output_tokens or 0 for item in items),
                    "cached_tokens": sum(item.cached_tokens or 0 for item in items),
                    "known_cost_usd": total_cost,
                    "known_cost_records": len(cost_rows),
                    "unknown_cost_records": len(unknown_cost),
                    "not_applicable_records": len(not_applicable),
                    "cost_coverage": round(len(cost_rows) / cost_denominator, 4)
                    if cost_denominator
                    else None,
                    "cost_denominator": cost_denominator,
                    "cost_per_record_usd": (total_cost / len(items)).quantize(Decimal("0.000001"))
                    if items
                    else None,
                },
                "functional": {
                    "scenario_ids": sorted(common_executed),
                    "sample_size": len(functional_rows),
                    "executed": len(functional_rows),
                    "approved": sum(1 for item in functional_rows if item.result == "approved"),
                    "failed": sum(1 for item in functional_rows if item.result == "failed"),
                    "success_rate": round(
                        sum(1 for item in functional_rows if item.result == "approved")
                        / len(functional_rows),
                        4,
                    )
                    if functional_rows
                    else None,
                    "success_denominator": len(functional_rows),
                    "structure_rate": round(
                        sum(
                            1
                            for item in functional_rows
                            if item.error_code not in {"invalid_model_output", "run_timeout"}
                        )
                        / len(functional_rows),
                        4,
                    )
                    if functional_rows
                    else 0,
                    "structure_denominator": len(functional_rows),
                    "median_latency_ms": int(statistics.median(durations)) if durations else None,
                    "latency_denominator": len(durations),
                    "input_tokens": sum(item.input_tokens or 0 for item in functional_rows),
                    "output_tokens": sum(item.output_tokens or 0 for item in functional_rows),
                    "quality_avg": round(float(sum(quality) / len(quality)), 2)
                    if quality
                    else None,
                    "quality_denominator": len(quality),
                    "tool_accuracy": round(
                        sum(1 for item in findings if item.findings_match) / len(findings),
                        4,
                    )
                    if findings
                    else None,
                    "tool_denominator": len(findings),
                    "abstention_correct": sum(
                        1 for item in abstention if item.abstention_ok is True
                    ),
                    "abstention_denominator": len(abstention),
                    "citation_validity": round(citation_valid / citation_emitted, 4)
                    if citation_emitted
                    else None,
                    "citation_denominator": citation_emitted,
                    "known_cost_usd": functional_cost,
                    "known_cost_records": len(functional_cost_rows),
                    "unknown_cost_records": len(functional_unknown),
                    "cost_denominator": functional_cost_denominator,
                    "cost_coverage": round(
                        len(functional_cost_rows) / functional_cost_denominator, 4
                    )
                    if functional_cost_denominator
                    else None,
                    "cost_per_scenario_usd": (functional_cost / len(functional_rows)).quantize(
                        Decimal("0.000001")
                    )
                    if functional_rows
                    else None,
                },
                "rows": {item.scenario: item for item in items},
            }
        )
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
                        "duration_ms": item["rows"][scenario].duration_ms
                        if scenario in item["rows"]
                        else None,
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
        "comparison_sample": {
            "ids": sorted(common_executed),
            "size": len(common_executed),
        },
        "missing": missing,
        "matrix": matrix,
        "provider_filter": provider,
        "notes": notes,
        "generated_at": utc_now_iso(),
    }
