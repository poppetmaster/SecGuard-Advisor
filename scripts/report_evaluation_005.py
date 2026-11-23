"""Regenera métricas e informe de la evaluación 005 sin llamadas de modelo.

Lee ``resultados-<proveedor>.json`` y ``casos.json`` de un directorio de
evidencia y reescribe ``resultados.json``, ``metricas.csv``, ``resumen.json`` y
``comparacion-proveedores.md``. No accede a la base de datos ni a la red.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from decimal import Decimal
from pathlib import Path

PROVIDERS = ("ollama", "deepseek", "anthropic")
LABELS = {
    "ollama": "Ollama (`qwen3.5:9b`)",
    "deepseek": "DeepSeek (`deepseek-flash`)",
    "anthropic": "Anthropic (`claude-haiku-5-5`)",
}
SCENARIO_LABELS = {
    "S01": "CSF 2.0",
    "S02": "AI RMF",
    "S03": "OWASP LLM",
    "S04": "Fuentes públicas combinadas",
    "S05": "Política ficticia",
    "S06": "Seguimiento de S05",
    "S07": "Hallazgos sintéticos por activo",
    "S08": "Hallazgos importados (severidad/explotabilidad)",
    "S09": "Abstención",
    "S10": "Informe breve",
}


def _valid_citations(row: dict) -> list[dict]:
    return [item for item in row["citations"] if item["check_status"] == "valid"]


def _quality_avg(row: dict) -> float:
    values = row["quality"]
    keys = ("accuracy", "relevance", "clarity", "recommendations", "uncertainty")
    return sum(values[key] for key in keys) / len(keys)


def _load(output: Path) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    for provider in PROVIDERS:
        path = output / f"resultados-{provider}.json"
        if path.exists():
            rows.extend(json.loads(path.read_text(encoding="utf-8")))
    casos = json.loads((output / "casos.json").read_text(encoding="utf-8"))
    return rows, casos


def _summary(rows: list[dict], provider: str, common_ids: set[str]) -> dict:
    own = [row for row in rows if row["provider"] == provider]
    executed = [row for row in own if row["result"] != "blocked"]
    functional = [row for row in executed if row["scenario"] in common_ids]
    approved = [row for row in functional if row["result"] == "approved"]
    failed = [row for row in functional if row["result"] == "failed"]
    blocked = [row for row in own if row["result"] == "blocked"]
    timeouts = [row for row in functional if row["error_code"] == "run_timeout"]
    durations = [row["duration_ms"] for row in functional if row["duration_ms"] is not None]
    stable = [
        row["duration_ms"]
        for row in functional
        if row["error_code"] != "run_timeout" and row["duration_ms"] is not None
    ]
    calculated = [
        Decimal(row["cost"]["usd"])
        for row in own
        if row["cost"]["status"] == "calculated" and row["cost"]["usd"] is not None
    ]
    unknown_cost = [row for row in own if row["cost"]["status"] == "unknown"]
    not_applicable = [row for row in own if row["cost"]["status"] == "not_applicable"]
    with_citations = [row for row in functional if row["citations"]]
    fully_valid = [
        row
        for row in with_citations
        if all(item["check_status"] == "valid" and item["resolvable"] for item in row["citations"])
    ]
    query_rows = [row for row in functional if row["scenario"] in {"S07", "S08"}]
    abstention_rows = [row for row in functional if row["scenario"] == "S09"]
    structure = [
        row
        for row in functional
        if row["structure_ok"]
        and row["error_code"] not in {"invalid_model_output", "run_timeout"}
        and row["status"] == "succeeded"
    ]
    known_total = sum(calculated) if calculated else None
    cost_denominator = len(calculated) + len(unknown_cost)
    quality_values = [_quality_avg(row) for row in functional]
    return {
        "provider": provider,
        "common_ids": sorted(common_ids),
        "common_size": len(common_ids),
        "consumption": {
            "records": len(own),
            "blocked": len(blocked),
            "input_tokens": sum(row["usage"]["input_tokens"] or 0 for row in own),
            "output_tokens": sum(row["usage"]["output_tokens"] or 0 for row in own),
            "cached_tokens": sum(row["usage"]["cached_tokens"] or 0 for row in own),
            "known_cost_usd": str(known_total) if known_total is not None else None,
            "known_cost_records": len(calculated),
            "unknown_cost_records": len(unknown_cost),
            "not_applicable_records": len(not_applicable),
            "cost_coverage": round(len(calculated) / cost_denominator, 4)
            if cost_denominator
            else None,
            "cost_denominator": cost_denominator,
            "cost_per_record_usd": str((known_total / len(own)).quantize(Decimal("0.000001")))
            if known_total is not None and own
            else None,
        },
        "functional": {
            "sample_ids": sorted(common_ids),
            "sample_size": len(common_ids),
            "executed": len(functional),
            "approved": len(approved),
            "failed": len(failed),
            "blocked": len(blocked),
            "success_rate": round(len(approved) / len(functional), 4) if functional else None,
            "success_denominator": len(functional),
            "timeouts": len(timeouts),
            "median_latency_ms": int(statistics.median(durations)) if durations else None,
            "median_latency_excluding_timeouts_ms": int(statistics.median(stable))
            if stable
            else None,
            "latency_denominator": len(durations),
            "mean_latency_ms": int(sum(durations) / len(durations)) if durations else None,
            "max_latency_ms": max(durations) if durations else None,
            "input_tokens": sum(row["usage"]["input_tokens"] or 0 for row in functional),
            "output_tokens": sum(row["usage"]["output_tokens"] or 0 for row in functional),
            "structure_rate": round(len(structure) / len(functional), 4) if functional else 0,
            "citation_rate": round(len(fully_valid) / len(with_citations), 4)
            if with_citations
            else None,
            "citation_runs": len(with_citations),
            "citation_runs_fully_valid": len(fully_valid),
            "query_accuracy": round(
                sum(1 for row in query_rows if row["findings_match"]) / len(query_rows), 4
            )
            if query_rows
            else None,
            "query_runs": len(query_rows),
            "abstention_correct": sum(1 for row in abstention_rows if row["abstention_ok"] is True),
            "abstention_runs": len(abstention_rows),
            "quality_avg": round(sum(quality_values) / len(quality_values), 2)
            if quality_values
            else None,
            "quality_denominator": len(quality_values),
        },
    }


def _csv_rows(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        steps = row.get("model_steps") or []
        decide = next((step["duration_ms"] for step in steps if step["name"] == "decide"), None)
        agent = next((step["duration_ms"] for step in steps if step["name"] == "agent"), None)
        valid = _valid_citations(row)
        out.append(
            {
                "provider": row["provider"],
                "model": row["model"],
                "identity": row["identity"],
                "scenario": row["scenario"],
                "kind": row["kind"],
                "run_id": row["run_id"],
                "result": row["result"],
                "status": row["status"],
                "outcome": row["outcome"],
                "error_code": row["error_code"],
                "wall_ms": row["duration_ms"],
                "generator_calls": row["model_calls"],
                "decide_ms": decide,
                "agent_ms": agent,
                "input_tokens": row["usage"]["input_tokens"],
                "output_tokens": row["usage"]["output_tokens"],
                "cached_tokens": row["usage"]["cached_tokens"],
                "usage_source": row["usage"]["source"],
                "cost_status": row["cost"]["status"],
                "cost_usd": row["cost"]["usd"],
                "tariff_version": row["cost"]["tariff_version"],
                "tool_calls": "|".join(
                    f"{item['tool']}:{item['status']}" for item in row["tool_calls"]
                ),
                "repairs": row["repairs"],
                "turn_attempts": 1,
                "structure_ok": row["structure_ok"],
                "structured_output_valid": bool(
                    row["structure_ok"]
                    and row["status"] == "succeeded"
                    and row["error_code"] not in {"invalid_model_output", "run_timeout"}
                ),
                "citations_emitted": len(row["citations"]),
                "citations_resolvable": sum(1 for item in row["citations"] if item["resolvable"]),
                "citations_validator_accepted": len(valid),
                "citations_byte_exact": sum(1 for item in row["citations"] if item["literal"]),
                "source_hit": row["source_hit"],
                "findings_match": row["findings_match"],
                "abstention_ok": row["abstention_ok"],
                "quality_avg_ai": round(_quality_avg(row), 2),
            }
        )
    return out


def _fmt(value, empty: str = "—") -> str:
    if value is None:
        return empty
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


def _coverage(value) -> str:
    return "sin registros con costo" if value is None else f"{value:.2%}"


def _percent(value, empty: str) -> str:
    return empty if value is None else f"{value:.2%}"


def _markdown(rows: list[dict], casos: dict, summaries: list[dict]) -> str:
    budget = casos["budget"]
    lines = [
        "# Comparación de proveedores — Evaluación 005",
        "",
        f"Conjunto `{casos['version']}` congelado el {casos['frozen_at']}; "
        f"hash `{casos['sha256']}`.",
        "",
        "Resultados **exploratorios**: 10 escenarios por proveedor no alcanzan para una "
        "conclusión estadística. La calidad 0-2 es una evaluación asistida por IA, no una "
        "revisión humana independiente.",
        "",
        "## Consumo completo por proveedor",
        "",
        "Todos los escenarios e intentos registrados, incluidos los bloqueados. El costo es el "
        "subtotal **conocido**: no es facturación completa y los registros desconocidos no se "
        "presentan como cero.",
        "",
        "| Proveedor | Registros | Bloqueados | Tokens E | Tokens S | Caché | "
        "Costo conocido | Costo / registro | Registros con costo | Desconocidos | No aplica | "
        "Cobertura de costo |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for summary in summaries:
        consumption = summary["consumption"]
        lines.append(
            f"| {LABELS[summary['provider']]} | {consumption['records']} | "
            f"{consumption['blocked']} | {consumption['input_tokens']} | "
            f"{consumption['output_tokens']} | {consumption['cached_tokens']} | "
            f"{_fmt(consumption['known_cost_usd'], 'sin cobro por API')} | "
            f"{_fmt(consumption['cost_per_record_usd'], '—')} | "
            f"{consumption['known_cost_records']} | "
            f"{consumption['unknown_cost_records']} | "
            f"{consumption['not_applicable_records']} | "
            f"{_coverage(consumption['cost_coverage'])} |"
        )
    lines += [
        "",
        "Los tokens incluyen escenarios bloqueados cuando la llamada se registró. Ollama no "
        "tiene cobro por API; no se declara costo operativo total cero.",
        "",
        "## Comparativo funcional — muestra común",
        "",
    ]
    sample_ids = summaries[0]["common_ids"] if summaries else []
    lines.append(
        f"Muestra común ejecutada: **{len(sample_ids)} escenarios** "
        f"({', '.join(sample_ids) if sample_ids else 'sin muestra'}). "
        "Éxito, latencia y calidad se recalculan solo sobre esta intersección."
    )
    lines += [
        "",
        "| Proveedor | Muestra | Aprobados | Fallidos | Éxito | Latencia mediana | "
        "Estructura | Citas válidas | Herramientas | Abstención | Calidad IA |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for summary in summaries:
        functional = summary["functional"]
        lines.append(
            f"| {LABELS[summary['provider']]} | {functional['executed']} | "
            f"{functional['approved']} | {functional['failed']} | "
            f"{functional['approved']}/{functional['success_denominator']} "
            f"({functional['success_rate']:.2%}) | "
            f"{_fmt(functional['median_latency_ms'])} ms "
            f"(n={functional['latency_denominator']}) | "
            f"{functional['structure_rate']:.2%} | "
            f"{_percent(functional['citation_rate'], 'sin citas')} "
            f"({functional['citation_runs_fully_valid']}/{functional['citation_runs']}) | "
            f"{_percent(functional['query_accuracy'], 'sin consultas')} "
            f"(n={functional['query_runs']}) | "
            f"{functional['abstention_correct']}/{functional['abstention_runs']} | "
            f"{_fmt(functional['quality_avg'])} (n={functional['quality_denominator']}) |"
        )
    lines += [
        "",
        "«Citas válidas» usa el validador del producto (`check_citation`, comparación "
        "normalizada) y exige cita resoluble. No prueba respaldo semántico. La columna "
        "`citations_byte_exact` de `metricas.csv` es más estricta y no representa un fallo.",
        "",
        "La calidad 0-2 es asistida por IA, no una revisión humana independiente.",
        "",
        "## Detalle por escenario",
    ]
    for provider in PROVIDERS:
        own = [row for row in rows if row["provider"] == provider]
        if not own:
            continue
        lines += [
            "",
            f"### {LABELS[provider]}",
            "",
            "| Escenario | Resultado | Salida | Error | Citas (válidas/emitidas) | "
            "Fuente esperada | Coincidencia SQL | ms | Costo |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for row in own:
            valid = len(_valid_citations(row))
            lines.append(
                f"| {row['scenario']} {SCENARIO_LABELS[row['scenario']]} | {row['result']} | "
                f"{row['outcome'] or '—'} | {row['error_code'] or '—'} | "
                f"{valid}/{len(row['citations'])} | "
                f"{_fmt(row['source_hit'])} | {_fmt(row['findings_match'])} | "
                f"{row['duration_ms']} | {_fmt(row['cost']['usd'])} |"
            )
    lines += [
        "",
        "## Presupuesto",
        "",
        f"- Presupuesto global: {budget['global_usd']} USD; por turno: "
        f"{budget['run_usd']} USD; tarifas `{budget['tariff_version']}`.",
        f"- Estimación previa: {json.dumps(casos.get('budget_estimate', {}), ensure_ascii=False)}.",
        f"- Ledger liquidado: {budget.get('spent_ledger_usd')} USD; uso observado: "
        f"{budget.get('spent_usage_usd')} USD.",
        f"- Restante conservador (ledger): {budget.get('remaining_ledger_usd')} USD.",
        "",
        "## Limitaciones",
        "",
        "- 10 escenarios por proveedor: muestra pequeña y exploratoria.",
        "- Sin evaluación semántica humana independiente; la calidad 0-2 es asistida por IA.",
        "- Corpus público y caso ficticio; no se usaron datos privados ni Qualys real.",
        "- Las llamadas externas se hicieron con proveedores reales; DeepSeek y Anthropic "
        "no exponen una versión de API en las respuestas registradas.",
        "- Los proveedores externos bloquean `findings_query` sobre datos importados "
        "(`external_tool_blocked`); S08 se registra como bloqueado, no como fallo.",
        "",
        "## Historial de iteraciones",
        "",
        "- `iteracion-1/`: primera pasada; el arnés exigía `source_id` en documentos de caso "
        "y limitaba la salida externa a 512 tokens. Conservada como evidencia.",
        "- `iteracion-2/`: segunda pasada con la coincidencia de fuentes corregida a mitad "
        "de la corrida; conservada como evidencia.",
        "- Raíz del directorio: tercera pasada, declarada como resultado de la evaluación.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output: Path = args.output_dir
    rows, casos = _load(output)
    if not rows:
        raise SystemExit("No hay resultados para regenerar.")
    spent = Decimal(str(casos["budget"].get("spent_ledger_usd") or 0))
    casos["budget"]["remaining_ledger_usd"] = str(
        Decimal(str(casos["budget"]["global_usd"])) - spent
    )
    (output / "casos.json").write_text(
        json.dumps(casos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output / "resultados.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    csv_rows = _csv_rows(rows)
    with (output / "metricas.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(csv_rows[0]))
        writer.writeheader()
        writer.writerows(csv_rows)
    providers_present = [
        provider for provider in PROVIDERS if any(row["provider"] == provider for row in rows)
    ]
    executed_sets = [
        {
            row["scenario"]
            for row in rows
            if row["provider"] == provider and row["result"] != "blocked"
        }
        for provider in providers_present
    ]
    common_ids = set.intersection(*executed_sets) if executed_sets else set()
    summaries = [_summary(rows, provider, common_ids) for provider in providers_present]
    (output / "resumen.json").write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output / "comparacion-proveedores.md").write_text(
        _markdown(rows, casos, summaries), encoding="utf-8"
    )
    print(json.dumps(summaries, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
