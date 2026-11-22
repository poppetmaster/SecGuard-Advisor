"""Tarifas fechadas y cálculo de costo por proveedor (005).

Los precios se verificaron el 2026-11-22 en documentación oficial. Deben
revalidarse antes de aceptar 005. Un uso o una tarifa ausente produce
``unknown``; nunca se inventa costo cero.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

TARIFF_VERSION = "2026-11-22"
USD = Decimal("0.000001")


class TariffUnavailable(RuntimeError):
    """No hay tarifa aplicable para reservar una llamada."""


@dataclass(frozen=True, slots=True)
class CostResult:
    status: str
    usd: Decimal | None
    tariff_version: str | None
    detail: dict


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(USD, rounding=ROUND_HALF_UP)


def _per_mtok(tokens: int, usd_per_mtok: Decimal) -> Decimal:
    return Decimal(tokens) * usd_per_mtok / Decimal(1_000_000)


def is_deepseek_peak(at: datetime) -> bool:
    """Peak: 01:00-04:00 y 06:00-10:00 UTC, lunes a viernes.

    No se modelan feriados chinos; se documenta como límite de la tarifa.
    """
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    at = at.astimezone(UTC)
    if at.weekday() >= 5:
        return False
    return 1 <= at.hour < 4 or 6 <= at.hour < 10


def _anthropic_rates(input_tokens: int) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    if input_tokens > 100_000:
        return Decimal("0.50"), Decimal("2.50"), Decimal("0.05"), Decimal("0.625")
    return Decimal("0.10"), Decimal("0.50"), Decimal("0.01"), Decimal("0.125")


def _deepseek_rates(peak: bool) -> tuple[Decimal, Decimal, Decimal]:
    multiplier = Decimal("2") if peak else Decimal("1")
    return (
        Decimal("0.15") * multiplier,
        Decimal("0.003") * multiplier,
        Decimal("0.60") * multiplier,
    )


def calculate_cost(
    provider: str,
    model: str,
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    cached_tokens: int | None = 0,
    cache_write_tokens: int | None = 0,
    at: datetime | None = None,
    tariff_version: str = TARIFF_VERSION,
) -> CostResult:
    if provider == "ollama":
        return CostResult("not_applicable", None, None, {"reason": "local"})
    if tariff_version != TARIFF_VERSION:
        return CostResult("unknown", None, None, {"reason": "tariff_mismatch"})
    if input_tokens is None or output_tokens is None:
        return CostResult("unknown", None, None, {"reason": "usage_missing"})
    at = at or datetime.now(UTC)
    cached = int(cached_tokens or 0)
    cache_write = int(cache_write_tokens or 0)
    if provider == "anthropic" and model == "claude-haiku-5-5":
        input_rate, output_rate, read_rate, write_rate = _anthropic_rates(input_tokens)
        total = (
            _per_mtok(input_tokens, input_rate)
            + _per_mtok(cached, read_rate)
            + _per_mtok(cache_write, write_rate)
            + _per_mtok(output_tokens, output_rate)
        )
        return CostResult(
            "calculated",
            _quantize(total),
            TARIFF_VERSION,
            {"tier": "over_100k" if input_tokens > 100_000 else "up_to_100k"},
        )
    if provider == "deepseek" and model == "deepseek-flash":
        peak = is_deepseek_peak(at)
        miss_rate, hit_rate, output_rate = _deepseek_rates(peak)
        miss_tokens = max(0, input_tokens - cached)
        total = (
            _per_mtok(miss_tokens, miss_rate)
            + _per_mtok(cached, hit_rate)
            + _per_mtok(output_tokens, output_rate)
        )
        return CostResult(
            "calculated",
            _quantize(total),
            TARIFF_VERSION,
            {"peak": peak, "cache_hit_tokens": cached},
        )
    return CostResult("unknown", None, None, {"reason": "tariff_missing"})


def reserve_amount(
    provider: str,
    model: str,
    *,
    input_tokens: int,
    max_output_tokens: int,
    at: datetime | None = None,
    tariff_version: str = TARIFF_VERSION,
) -> Decimal:
    """Reserva conservadora: entrada estimada + salida máxima."""
    if tariff_version != TARIFF_VERSION:
        raise TariffUnavailable("La versión de tarifa no está disponible.")
    if input_tokens < 0 or max_output_tokens <= 0:
        raise TariffUnavailable("Los límites para reservar no son válidos.")
    at = at or datetime.now(UTC)
    if provider == "anthropic" and model == "claude-haiku-5-5":
        input_rate, output_rate, _, _ = _anthropic_rates(input_tokens)
        return _quantize(
            _per_mtok(input_tokens, input_rate) + _per_mtok(max_output_tokens, output_rate)
        )
    if provider == "deepseek" and model == "deepseek-flash":
        miss_rate, _, output_rate = _deepseek_rates(is_deepseek_peak(at))
        return _quantize(
            _per_mtok(input_tokens, miss_rate) + _per_mtok(max_output_tokens, output_rate)
        )
    raise TariffUnavailable("No hay tarifa aplicable para el proveedor y modelo.")
