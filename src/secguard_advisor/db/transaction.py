"""Unidad de trabajo de transacción corta."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session, sessionmaker


class ActiveTransactionError(RuntimeError):
    """Hay una transacción abierta donde no debería haberla."""


@contextmanager
def unit_of_work(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Abre una sesión, confirma al salir y siempre la cierra."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ensure_no_active_transaction(session: Session) -> None:
    """Falla si la sesión ya tiene una transacción abierta."""
    if session.in_transaction():
        raise ActiveTransactionError("Hay una transacción activa antes de la llamada al modelo.")
