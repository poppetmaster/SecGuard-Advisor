"""Controles de concurrencia: exclusión por caso y permiso global de generación."""

from __future__ import annotations

import threading

from sqlalchemy import select
from sqlalchemy.orm import Session

from secguard_advisor.db.models import Run


class GenerationBusy(RuntimeError):
    """Otra generación ocupa el permiso global y la espera se agotó."""


class CaseBusy(RuntimeError):
    """El caso ya tiene una ejecución activa."""


class GenerationSlot:
    """Permiso global de una sola generación, con espera acotada.

    Se adquiere antes de crear la ejecución y se libera en ``finally`` cuando la
    generación terminó de verdad. La desconexión del cliente no lo libera.
    """

    def __init__(self, timeout_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds
        self._semaphore = threading.BoundedSemaphore(1)

    def acquire(self, timeout: float | None = None) -> bool:
        return self._semaphore.acquire(timeout=self.timeout_seconds if timeout is None else timeout)

    def release(self) -> None:
        self._semaphore.release()

    @property
    def held(self) -> bool:
        if not self._semaphore.acquire(blocking=False):
            return True
        self._semaphore.release()
        return False


def find_active_run(session: Session, case_id: str) -> Run | None:
    """Devuelve la ejecución en curso del caso, si existe."""
    return session.scalar(select(Run).where(Run.case_id == case_id, Run.status == "running"))
