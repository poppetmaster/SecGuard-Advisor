"""Reevaluación externa focalizada de 005, con tope adicional de 0,10 USD.

Uso:
    SECGUARD_EXTERNAL_TESTS_AUTHORIZED=1 uv run python scripts/reevaluate_external_005.py \
        --output-dir docs/evidencia/005-estabilizacion/reevaluacion-externa

El script usa una instancia temporal, corpus público y casos ficticios. No
imprime claves ni prompts. No reintenta escenarios del arnés.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tempfile
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.evaluate_providers_005 import (
    MAX_OUTPUT_EXTERNAL,
    MODELS,
    _base_settings,
    _close,
    _collect,
    _expected_synthetic,
    _new_case,
    _prepare,
)
from tests.fixtures.evaluation_005 import SCENARIOS

from secguard_advisor.ai_config.service import (
    resolve_turn_settings,
    save_configuration,
)
from secguard_advisor.cases.external import authorize_case
from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.conversation.memory import open_memory
from secguard_advisor.conversation.providers.context import build_prompt_counter
from secguard_advisor.conversation.providers.cost import reserve_amount
from secguard_advisor.conversation.providers.registry import ProviderRegistry
from secguard_advisor.conversation.turn import execute_turn, start_question_turn
from secguard_advisor.db.models import (
    AiRequest,
    ProviderBudgetLedger,
    Run,
)

MAX_EXTRA_USD = Decimal("0.10")
MAX_CALLS_PER_SCENARIO = 4
ESTIMATED_INPUT_TOKENS = 4000
PLAN = {
    "deepseek": ("S03", "S04"),
    "anthropic": ("S02", "S03", "S04", "S07", "S10"),
}
SCENARIO_BY_ID = {scenario["id"]: scenario for scenario in SCENARIOS}


def _estimates(settings: Settings, cap: Decimal) -> dict:
    at = datetime.now(UTC)
    result = {}
    total = Decimal("0")
    for provider, scenario_ids in PLAN.items():
        per_call = reserve_amount(
            provider,
            MODELS[provider],
            input_tokens=ESTIMATED_INPUT_TOKENS,
            max_output_tokens=MAX_OUTPUT_EXTERNAL,
            at=at,
            tariff_version=settings.external_tariff_version,
        )
        provider_total = per_call * MAX_CALLS_PER_SCENARIO * len(scenario_ids)
        result[provider] = {
            "per_call_usd": str(per_call),
            "max_calls": MAX_CALLS_PER_SCENARIO * len(scenario_ids),
            "worst_case_usd": str(provider_total),
        }
        total += provider_total
    return {"cap_usd": str(cap), "worst_case_usd": str(total), "providers": result}


def _safe_error(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:300]}"


def _request_rows(factory, run_id: str) -> list[dict]:
    with factory() as session:
        rows = list(
            session.scalars(
                select(AiRequest).where(AiRequest.run_id == run_id).order_by(AiRequest.started_at)
            )
        )
    return [
        {
            "operation": row.operation,
            "attempt": row.attempt_no,
            "provider": row.provider,
            "model": row.model,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
            "status": row.status,
            "duration_ms": row.duration_ms,
            "input_tokens": row.input_tokens,
            "output_tokens": row.output_tokens,
            "cached_tokens": row.cached_tokens,
            "reasoning_tokens": row.reasoning_tokens,
            "usage_source": row.usage_source,
            "cost_status": row.cost_status,
            "cost_usd": str(row.cost_usd) if row.cost_usd is not None else None,
            "currency": row.currency,
            "tariff_version": row.tariff_version,
            "error_code": row.error_code,
        }
        for row in rows
    ]


def _run_scenario(
    factory,
    settings: Settings,
    provider: str,
    scenario: dict,
    embedder,
    index,
    memory,
) -> dict:
    case_id = _new_case(factory, provider, scenario, embedder, index)
    with factory() as session:
        authorize_case(
            session,
            case_id=case_id,
            scope="fictional_case",
            authorized_by="Reevaluación externa 005",
        )
        session.commit()
    expected = {}
    if scenario["id"] == "S07":
        expected = _expected_synthetic(factory, case_id)
    with factory() as session:
        turn_settings = resolve_turn_settings(session, settings)
    generator = ProviderRegistry(turn_settings).create()
    counter = build_prompt_counter(turn_settings)
    started = time.perf_counter()
    try:
        context = start_question_turn(
            factory,
            turn_settings,
            scope=CaseScope(case_id=case_id),
            question=scenario["question"],
            generator=generator,
            embedder=embedder,
            index=index,
            token_counter=counter,
        )
        result = execute_turn(context, memory=memory)
        row = _collect(factory, scenario, context, result, started, expected)
        row["case_id"] = case_id
        row["run_id"] = context.run_id
        row["provider"] = provider
        row["scenario_id"] = scenario["id"]
        row["request_details"] = _request_rows(factory, context.run_id)
        row["requests"] = len(row["request_details"])
        row["known_cost_usd"] = str(
            sum(
                Decimal(item["cost_usd"])
                for item in row["request_details"]
                if item["cost_usd"] is not None
            )
        )
        row["unknown_cost_requests"] = sum(
            1 for item in row["request_details"] if item["cost_status"] == "unknown"
        )
        with factory() as session:
            run = session.get(Run, context.run_id)
            row["error_message"] = run.error_message if run else None
        reason = None
        if row["error_message"] and "Motivo:" in row["error_message"]:
            reason = row["error_message"].split("Motivo:", 1)[1].strip().rstrip(".")
        for request in row["request_details"]:
            request["error_reason"] = reason if request["status"] == "error" else None
        return row
    finally:
        _close(generator)
        _close(counter)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get("SECGUARD_EXTERNAL_TESTS_AUTHORIZED") != "1":
        print(
            "Detenido: falta SECGUARD_EXTERNAL_TESTS_AUTHORIZED=1. No se envió ninguna solicitud."
        )
        return 2
    base = _base_settings()
    if base.deepseek_api_key is None or base.anthropic_api_key is None:
        print("Detenido: faltan credenciales externas. No se envió ninguna solicitud.")
        return 2
    cap = min(MAX_EXTRA_USD, base.external_budget_usd, base.external_run_budget_usd)
    if cap <= 0:
        print("Detenido: no hay presupuesto externo disponible.")
        return 2
    estimate = _estimates(base, cap)
    if Decimal(estimate["worst_case_usd"]) > cap:
        print(
            "Detenido antes de llamar: el peor caso estimado "
            f"{estimate['worst_case_usd']} USD supera el tope {cap} USD."
        )
        return 2
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    report_rows: list[dict] = []
    stop_reason = None
    with tempfile.TemporaryDirectory(prefix="reeval-external-005-") as directory:
        root = Path(directory)
        settings, factory, embedder, index = _prepare(root, base)
        capped = settings.model_copy(
            update={
                "external_budget_usd": cap,
                "external_run_budget_usd": cap,
            }
        )
        memory = open_memory(capped.checkpoints_path)
        try:
            for provider, scenario_ids in PLAN.items():
                with factory() as session:
                    save_configuration(
                        session,
                        capped,
                        provider=provider,
                        model=MODELS[provider],
                        max_output_tokens=MAX_OUTPUT_EXTERNAL,
                        timeout_seconds=90,
                    )
                    session.commit()
                for scenario_id in scenario_ids:
                    try:
                        row = _run_scenario(
                            factory,
                            capped,
                            provider,
                            SCENARIO_BY_ID[scenario_id],
                            embedder,
                            index,
                            memory,
                        )
                    except Exception as exc:
                        report_rows.append(
                            {
                                "provider": provider,
                                "scenario_id": scenario_id,
                                "result": "failed",
                                "error_message": _safe_error(exc),
                                "request_details": [],
                            }
                        )
                        continue
                    report_rows.append(row)
        finally:
            memory.close()
            _close(embedder)
            _close(index)
        with factory() as session:
            spent = session.scalar(
                select(func.coalesce(func.sum(ProviderBudgetLedger.settled_usd), 0))
            )
        if Decimal(str(spent or 0)) > cap:
            stop_reason = "tope de presupuesto excedido; revisar el ledger"
    calls = [
        {
            "provider": row["provider"],
            "model": row.get("model"),
            "scenario": row["scenario_id"],
            **request,
        }
        for row in report_rows
        for request in row.get("request_details", ())
    ]
    (output / "resultados.json").write_text(
        json.dumps(report_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (output / "llamadas.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = [
            "provider",
            "model",
            "scenario",
            "operation",
            "status",
            "duration_ms",
            "input_tokens",
            "output_tokens",
            "cached_tokens",
            "reasoning_tokens",
            "usage_source",
            "cost_status",
            "cost_usd",
            "currency",
            "tariff_version",
            "error_code",
            "error_reason",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: call.get(key) for key in fields} for call in calls)
    known = sum(Decimal(call["cost_usd"]) for call in calls if call.get("cost_usd") is not None)
    summary = {
        "kind": "focalized_external_reevaluation",
        "dataset": "005-evaluation-v1",
        "scenarios": PLAN,
        "cap_usd": str(cap),
        "estimate": estimate,
        "known_cost_usd": str(known),
        "ledger_settled_usd": str(spent or 0),
        "requests": len(calls),
        "unknown_cost_requests": sum(1 for call in calls if call.get("cost_status") == "unknown"),
        "stop_reason": stop_reason,
        "completed_at": datetime.now(UTC).isoformat(),
    }
    (output / "resumen.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
