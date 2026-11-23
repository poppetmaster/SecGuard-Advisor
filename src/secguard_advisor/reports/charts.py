"""ECharts option builders shared by the web view and the PDF renderer."""

from __future__ import annotations

from typing import Any

from secguard_advisor.reports.privacy import INDICATOR_LABELS, SEVERITY_LABELS


def _percent(value: int, denominator: int) -> int:
    return round((value / denominator) * 100) if denominator else 0


def _severity_conclusion(dataset: dict[str, Any]) -> str:
    levels = dataset["severity"]["levels"]
    pending = sum(level["pending"] for level in levels)
    severe = sum(level["pending"] for level in levels if level["level"] >= 3)
    if not pending:
        return "No hay registros pendientes en la instantánea seleccionada."
    return (
        f"El {_percent(severe, pending)} % de los registros pendientes "
        "es de severidad 3 o superior."
    )


def _assets_conclusion(dataset: dict[str, Any]) -> str:
    top = dataset["assets_top"]
    if not top["assets_with_critical_or_high"]:
        return "No hay registros críticos o altos pendientes asociados a activos identificables."
    shown = min(top["top_n"], top["assets_with_critical_or_high"])
    records = sum(item["total"] for item in top["items"])
    total = top["records_critical_or_high"]
    return (
        f"{shown} activos concentran {records} de {total} registros críticos/altos "
        f"({_percent(records, total)} %)."
    )


def _indicator_conclusion(dataset: dict[str, Any], key: str, label: str) -> str:
    values = dataset[key]
    denominator = values["denominator"]
    positive = values["positive"]
    indeterminate = values["indeterminate"]
    return (
        f"{positive} de {denominator} registros pendientes tienen {label} positiva; "
        f"{indeterminate} quedan indeterminados."
    )


def build_chart_specs(dataset: dict[str, Any]) -> dict[str, Any]:
    """Return serializable ECharts options with deterministic conclusions."""
    severity = dataset["severity"]
    levels = severity["levels"]
    severity_option = {
        "animation": False,
        "color": ["#dc2626", "#475569"],
        "tooltip": {"trigger": "axis"},
        "legend": {"data": ["Pendientes", "Fixed"]},
        "grid": {"left": 40, "right": 16, "top": 36, "bottom": 30},
        "xAxis": {
            "type": "category",
            "data": [f"{item['level']} {SEVERITY_LABELS[item['level']]}" for item in levels],
            "axisLabel": {"fontSize": 11},
        },
        "yAxis": {"type": "value", "name": "Registros"},
        "series": [
            {"name": "Pendientes", "type": "bar", "data": [item["pending"] for item in levels]},
            {"name": "Fixed", "type": "bar", "data": [item["fixed"] for item in levels]},
        ],
    }

    assets = dataset["assets_top"]
    asset_labels = [item["alias"] for item in assets["items"]]
    asset_option = {
        "animation": False,
        "color": ["#b91c1c", "#ea580c"],
        "tooltip": {"trigger": "axis"},
        "legend": {"data": ["Críticas", "Altas"]},
        "grid": {"left": 90, "right": 16, "top": 36, "bottom": 30},
        "xAxis": {"type": "value", "name": "Registros"},
        "yAxis": {"type": "category", "data": list(reversed(asset_labels))},
        "series": [
            {
                "name": "Críticas",
                "type": "bar",
                "data": list(reversed([item["critical"] for item in assets["items"]])),
            },
            {
                "name": "Altas",
                "type": "bar",
                "data": list(reversed([item["high"] for item in assets["items"]])),
            },
        ],
    }

    def indicator_option(key: str) -> dict[str, Any]:
        values = dataset[key]
        categories = ["positive", "negative_no_info", "indeterminate"]
        return {
            "animation": False,
            "color": ["#dc2626", "#16a34a", "#d97706"],
            "tooltip": {"trigger": "axis"},
            "grid": {"left": 40, "right": 16, "top": 24, "bottom": 50},
            "xAxis": {
                "type": "category",
                "data": [INDICATOR_LABELS[item] for item in categories],
                "axisLabel": {"fontSize": 10, "interval": 0, "rotate": 15},
            },
            "yAxis": {"type": "value", "name": "Registros"},
            "series": [
                {
                    "type": "bar",
                    "data": [values[item] for item in categories],
                }
            ],
        }

    return {
        "schema_version": "report-charts-v1",
        "severity": {
            "title": "Distribución de severidad de los registros",
            "conclusion": _severity_conclusion(dataset),
            "denominator_label": (
                f"Base: {severity['denominator_pending']} pendientes y "
                f"{severity['denominator_fixed']} Fixed."
            ),
            "option": severity_option,
        },
        "assets": {
            "title": "Activos con mayor concentración de críticos y altos",
            "conclusion": _assets_conclusion(dataset),
            "denominator_label": (
                f"Activos con críticos/altos: {assets['assets_with_critical_or_high']}; "
                f"se muestran hasta {assets['top_n']}; total de registros: "
                f"{assets['records_critical_or_high']}."
            ),
            "option": asset_option,
        },
        "exploitability": {
            "title": "Explotabilidad en registros pendientes",
            "conclusion": _indicator_conclusion(dataset, "exploitability", "explotabilidad"),
            "denominator_label": f"Base: {dataset['exploitability']['denominator']} pendientes.",
            "option": indicator_option("exploitability"),
        },
        "malware": {
            "title": "Malware asociado en registros pendientes",
            "conclusion": _indicator_conclusion(dataset, "malware", "malware"),
            "denominator_label": f"Base: {dataset['malware']['denominator']} pendientes.",
            "option": indicator_option("malware"),
        },
    }
