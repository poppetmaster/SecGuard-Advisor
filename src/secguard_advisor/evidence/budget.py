"""Reserva y liquidación de presupuesto externo (005).

El saldo global y el saldo acumulado del turno son límites distintos. Una
llamada enviada con uso desconocido conserva la reserva comprometida; nunca se
libera como gasto cero.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from secguard_advisor.config import Settings
from secguard_advisor.conversation.providers.cost import (
    CostResult,
    calculate_cost,
    reserve_amount,
)
from secguard_advisor.db.models import ProviderBudgetLedger, Run, utc_now_iso

COMMITTED_STATES = ("settled", "reserved", "reconciled")


class BudgetExceeded(RuntimeError):
    code = "budget_exceeded"


@dataclass(frozen=True, slots=True)
class Reservation:
    id: str
    reserved_usd: Decimal


def _committed(session: Session, *, run_id: str | None = None) -> Decimal:
    statement = select(
        func.coalesce(
            func.sum(
                func.coalesce(ProviderBudgetLedger.settled_usd, ProviderBudgetLedger.reserved_usd)
            ),
            0,
        )
    ).where(ProviderBudgetLedger.state.in_(COMMITTED_STATES))
    if run_id is not None:
        statement = statement.where(ProviderBudgetLedger.run_id == run_id)
    value = session.scalar(statement) or 0
    return Decimal(str(value))


def ensure_budget_available(
    session: Session, settings: Settings, *, run_id: str | None = None
) -> None:
    """Comprueba saldo antes de cualquier envío, incluido el conteo externo."""
    global_budget = settings.external_budget_usd
    run_budget = settings.external_run_budget_usd
    if global_budget <= 0 or run_budget <= 0:
        raise BudgetExceeded("El presupuesto externo no está habilitado.")
    if _committed(session) >= global_budget:
        raise BudgetExceeded("El saldo global de presupuesto externo no alcanza.")
    if run_id is not None and _committed(session, run_id=run_id) >= run_budget:
        raise BudgetExceeded("El saldo del turno no alcanza para otra llamada externa.")


def begin_call(
    session: Session,
    *,
    settings: Settings,
    run_id: str,
    attempt_no: int,
    provider: str,
    model: str,
    input_tokens: int,
    max_output_tokens: int,
    at: datetime | None = None,
) -> Reservation:
    """Reserva el costo máximo antes de enviar. Falla cerrado si no cabe."""
    at = at or datetime.now(UTC)
    amount = reserve_amount(
        provider,
        model,
        input_tokens=input_tokens,
        max_output_tokens=max_output_tokens,
        at=at,
        tariff_version=settings.external_tariff_version,
    )
    global_budget = settings.external_budget_usd
    run_budget = settings.external_run_budget_usd
    if global_budget <= 0 or run_budget <= 0:
        raise BudgetExceeded("El presupuesto externo no está habilitado.")
    if _committed(session) + amount > global_budget:
        raise BudgetExceeded("El saldo global de presupuesto externo no alcanza.")
    if _committed(session, run_id=run_id) + amount > run_budget:
        raise BudgetExceeded("El saldo del turno no alcanza para otra llamada externa.")
    entry = ProviderBudgetLedger(
        run_id=run_id,
        attempt_no=attempt_no,
        provider=provider,
        model=model,
        state="reserved",
        reserved_usd=amount,
    )
    session.add(entry)
    session.flush()
    return Reservation(id=entry.id, reserved_usd=amount)


def settle_call(
    session: Session,
    reservation: Reservation,
    *,
    provider: str,
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
    cached_tokens: int | None,
    cache_write_tokens: int | None,
    tariff_version: str,
    at: datetime | None = None,
) -> CostResult:
    """Liquida con el uso observado; si falta, conserva la reserva."""
    entry = session.get(ProviderBudgetLedger, reservation.id)
    if entry is None:
        raise ValueError("La reserva no existe.")
    if entry.state != "reserved":
        raise ValueError("La reserva ya fue liquidada.")
    result = calculate_cost(
        provider,
        model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_tokens=cached_tokens,
        cache_write_tokens=cache_write_tokens,
        at=at,
        tariff_version=tariff_version,
    )
    entry.updated_at = utc_now_iso()
    if result.status == "calculated" and result.usd is not None:
        entry.state = "settled"
        entry.settled_usd = result.usd
    else:
        entry.state = "reconciled"
        entry.settled_usd = entry.reserved_usd
    session.flush()
    return result


def reconcile_call(session: Session, reservation: Reservation) -> None:
    """Conserva la reserva ante un envío incierto o un error."""
    entry = session.get(ProviderBudgetLedger, reservation.id)
    if entry is None or entry.state != "reserved":
        return
    entry.state = "reconciled"
    entry.settled_usd = entry.reserved_usd
    entry.updated_at = utc_now_iso()
    session.flush()


def release_call(session: Session, reservation: Reservation) -> None:
    """Libera una reserva solo cuando consta que la llamada no se envió."""
    entry = session.get(ProviderBudgetLedger, reservation.id)
    if entry is None or entry.state != "reserved":
        return
    entry.state = "released"
    entry.settled_usd = Decimal("0")
    entry.updated_at = utc_now_iso()
    session.flush()


def reconcile_startup(session: Session) -> int:
    """Reservas abiertas de ejecuciones terminales quedan comprometidas."""
    rows = list(
        session.scalars(
            select(ProviderBudgetLedger)
            .join(Run, Run.id == ProviderBudgetLedger.run_id)
            .where(
                ProviderBudgetLedger.state == "reserved",
                Run.status != "running",
            )
        )
    )
    for entry in rows:
        entry.state = "reconciled"
        entry.settled_usd = entry.reserved_usd
        entry.updated_at = utc_now_iso()
    session.flush()
    return len(rows)
