"""Regresiones del informe derivado de la evaluación 005."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

EVIDENCE = Path("docs/evidencia/005-evaluacion-proveedores")
PROVIDERS = ("ollama", "deepseek", "anthropic")


def _module():
    path = Path("scripts/report_evaluation_005.py")
    spec = importlib.util.spec_from_file_location("report_evaluation_005", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _data():
    rows = []
    for provider in PROVIDERS:
        rows.extend(
            json.loads((EVIDENCE / f"resultados-{provider}.json").read_text(encoding="utf-8"))
        )
    casos = json.loads((EVIDENCE / "casos.json").read_text(encoding="utf-8"))
    executed_sets = [
        {
            row["scenario"]
            for row in rows
            if row["provider"] == provider and row["result"] != "blocked"
        }
        for provider in PROVIDERS
    ]
    common = set.intersection(*executed_sets)
    return rows, casos, common


def test_report_keeps_blocked_consumption_and_common_sample() -> None:
    module = _module()
    rows, casos, common = _data()
    summaries = [module._summary(rows, provider, common) for provider in PROVIDERS]
    by_provider = {item["provider"]: item for item in summaries}

    assert by_provider["deepseek"]["consumption"]["known_cost_usd"] == "0.006201"
    assert by_provider["deepseek"]["consumption"]["unknown_cost_records"] == 2
    assert by_provider["anthropic"]["consumption"]["known_cost_usd"] == "0.006150"
    assert by_provider["anthropic"]["consumption"]["unknown_cost_records"] == 3
    assert by_provider["deepseek"]["functional"]["success_denominator"] == 9
    assert by_provider["deepseek"]["functional"]["success_rate"] == round(6 / 9, 4)
    assert by_provider["anthropic"]["functional"]["success_rate"] == round(4 / 9, 4)
    assert by_provider["ollama"]["functional"]["success_rate"] == round(5 / 9, 4)

    markdown = module._markdown(rows, casos, summaries)
    assert "Consumo completo por proveedor" in markdown
    assert "Costo conocido" in markdown
    assert "0.006201" in markdown
    assert "Muestra común ejecutada: **9 escenarios**" in markdown
    assert "6/9" in markdown
