"""Costos por proveedor con tarifa fechada (Entrega 2)."""

from datetime import UTC, datetime
from decimal import Decimal

from secguard_advisor.conversation.providers.cost import (
    TARIFF_VERSION,
    calculate_cost,
    is_deepseek_peak,
    reserve_amount,
)

OFF_PEAK = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)  # domingo
PEAK = datetime(2026, 11, 23, 2, 0, tzinfo=UTC)  # lunes 02:00 UTC


def test_anthropic_uses_the_up_to_100k_tier() -> None:
    result = calculate_cost(
        "anthropic",
        "claude-haiku-5-5",
        input_tokens=1000,
        output_tokens=500,
        at=OFF_PEAK,
    )

    assert result.status == "calculated"
    assert result.usd == Decimal("0.000350")
    assert result.detail["tier"] == "up_to_100k"


def test_anthropic_uses_the_over_100k_tier() -> None:
    result = calculate_cost(
        "anthropic",
        "claude-haiku-5-5",
        input_tokens=200_000,
        output_tokens=1_000,
        at=OFF_PEAK,
    )

    assert result.status == "calculated"
    assert result.usd == Decimal("0.102500")
    assert result.detail["tier"] == "over_100k"


def test_deepseek_off_peak_and_cache_hit() -> None:
    result = calculate_cost(
        "deepseek",
        "deepseek-flash",
        input_tokens=1000,
        output_tokens=500,
        cached_tokens=200,
        at=OFF_PEAK,
    )

    assert result.status == "calculated"
    assert result.usd == Decimal("0.000421")
    assert result.detail["peak"] is False


def test_deepseek_peak_doubles_the_rate() -> None:
    assert is_deepseek_peak(PEAK)
    result = calculate_cost(
        "deepseek",
        "deepseek-flash",
        input_tokens=1000,
        output_tokens=500,
        cached_tokens=0,
        at=PEAK,
    )

    assert result.status == "calculated"
    assert result.usd == Decimal("0.000900")
    assert result.detail["peak"] is True


def test_missing_usage_is_unknown_not_zero() -> None:
    result = calculate_cost("deepseek", "deepseek-flash", input_tokens=None, output_tokens=10)

    assert result.status == "unknown"
    assert result.usd is None


def test_unknown_tariff_version_is_unknown() -> None:
    result = calculate_cost(
        "anthropic",
        "claude-haiku-5-5",
        input_tokens=10,
        output_tokens=10,
        tariff_version="2099-01-01",
    )

    assert result.status == "unknown"
    assert result.usd is None


def test_ollama_cost_is_not_applicable() -> None:
    result = calculate_cost("ollama", "qwen3.5:9b", input_tokens=10, output_tokens=10)

    assert result.status == "not_applicable"
    assert result.usd is None


def test_reserve_amount_is_positive_for_external_providers() -> None:
    assert reserve_amount(
        "anthropic",
        "claude-haiku-5-5",
        input_tokens=1000,
        max_output_tokens=1200,
        at=OFF_PEAK,
    ) == Decimal("0.000700")
    assert reserve_amount(
        "deepseek",
        "deepseek-flash",
        input_tokens=1000,
        max_output_tokens=1200,
        at=OFF_PEAK,
    ) == Decimal("0.000870")
    assert TARIFF_VERSION == "2026-11-22"
