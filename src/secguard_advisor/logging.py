"""Configuración de logging del proyecto."""

import logging
from typing import Any

_SECRET_KEYS = frozenset({"api_key", "authorization", "password", "secret", "token"})
_FORMAT = (
    "%(asctime)s %(levelname)s %(name)s "
    "run_id=%(run_id)s case_id=%(case_id)s event=%(event)s %(message)s"
)


class ContextFilter(logging.Filter):
    """Añade contexto de ejecución y redacta claves sensibles."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = getattr(record, "run_id", "-")
        record.case_id = getattr(record, "case_id", "-")
        record.event = getattr(record, "event", "-")
        for key in _SECRET_KEYS:
            if hasattr(record, key):
                setattr(record, key, "***")
        if isinstance(record.args, dict):
            record.args = {
                key: ("***" if key.lower() in _SECRET_KEYS else value)
                for key, value in record.args.items()
            }
        return True


def configure_logging(level: int | str = logging.INFO) -> None:
    """Configura el logger raíz con el formato del proyecto."""
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(_FORMAT))
    handler.addFilter(ContextFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """Devuelve un logger con el contexto del proyecto."""
    return logging.getLogger(name)


def log_event(logger: logging.Logger, event: str, **context: Any) -> None:
    """Registra un evento operativo con contexto acotado."""
    logger.info("%s", event, extra={"event": event, **context})
