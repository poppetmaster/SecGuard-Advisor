"""Coherencia entre gráficas, tarjetas y tablas del panel de uso."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from tests.unit.test_ai_usage_queries import (  # helpers compartidos del panel
    _evaluation,
    _factory,
    _seed,
    _view,
)

from secguard_advisor.ai_usage.charts import (
    build_comparison_charts,
    build_consumption_charts,
)
from secguard_advisor.ai_usage.evaluations import build_comparison_view


def test_consumption_charts_match_cards_and_providers(tmp_path) -> None:
    factory = _factory(tmp_path)
    _seed(factory)
    view = _view(factory, from_date=date(2026, 1, 1), to_date=date(2026, 1, 31))

    charts = build_consumption_charts(view)

    cost_total = sum(
        point["value"]
        for series in charts["cost"]["series"]
        for point in series["data"]
        if point is not None
    )
    external_cost = sum(row["cost_usd"] for row in view["providers"] if row["provider"] != "ollama")
    assert cost_total == float(external_cost)

    request_total = sum(
        value for series in charts["requests"]["series"] for value in series["data"]
    )
    assert request_total == (view["cards"]["external_requests"] + view["cards"]["local_calls"])

    token_input = sum(item["input"] for item in charts["tokens"]["providers"])
    token_output = sum(item["output"] for item in charts["tokens"]["providers"])
    assert token_input == view["cards"]["input_tokens"]
    assert token_output == view["cards"]["output_tokens"]


def test_cost_chart_excludes_ollama_and_uses_null_for_unknown(tmp_path) -> None:
    factory = _factory(tmp_path)
    _seed(factory)
    view = _view(factory, from_date=date(2026, 1, 1), to_date=date(2026, 1, 31))

    charts = build_consumption_charts(view)

    assert {series["key"] for series in charts["cost"]["series"]} == {"deepseek"}
    values = charts["cost"]["series"][0]["data"]
    assert any(value is None for value in values)
    assert all(value is None or value["value"] > 0 for value in values)


def test_comparison_charts_recompute_on_common_sample(tmp_path) -> None:
    factory = _factory(tmp_path)
    with factory() as session:
        _evaluation(session)
        view = build_comparison_view(session, evaluation_id="eval-1")

    charts = build_comparison_charts(view)

    by_provider = {item["key"]: item for item in charts["results"]}
    assert sum(by_provider["deepseek"][key] for key in ("approved", "failed", "blocked")) == 3
    deepseek = next(item for item in view["providers"] if item["provider"] == "deepseek")
    latency = next(item for item in charts["latency"] if item["key"] == "deepseek")
    assert latency["seconds"] == round(deepseek["functional"]["median_latency_ms"] / 1000, 3)
    assert {item["key"] for item in charts["cost"]} == {"deepseek", "anthropic"}
    deepseek_cost = next(item for item in charts["cost"] if item["key"] == "deepseek")
    assert deepseek_cost["value"] == float(deepseek["functional"]["cost_per_scenario_usd"])
    assert deepseek_cost["coverage"] == "2/2 escenarios con costo conocido"
    assert len(charts["matrix"]["cells"]) == 9
    assert charts["quality"]["available"] is False
    assert all(cell["duration_ms"] is not None for cell in charts["matrix"]["cells"])
    assert Decimal(str(deepseek_cost["value"])) == Decimal("0.002")
