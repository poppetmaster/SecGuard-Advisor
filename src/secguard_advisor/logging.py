"""Configuración de logging del proyecto."""

import logging
import re
from typing import Any

_SECRET_KEYS = frozenset({"api_key", "authorization", "password", "secret", "token"})
_PATH_PATTERN = re.compile(r"(?:/(?:Users|home|private|tmp|var)/[^\s\"']+)")
_SECRET_PATTERN = re.compile(r"\b(?:lsv2_|sk-)[A-Za-z0-9_-]{8,}\b")
_FORMAT = (
    "%(asctime)s %(levelname)s %(name)s "
    "run_id=%(run_id)s case_id=%(case_id)s event=%(event)s %(message)s"
)
_STANDARD_ATTRS = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "taskName",
        "message",
        "asctime",
    }
)


def _redact(value: Any) -> Any:
    """Redacta secretos, rutas absolutas y trazas de pila en cualquier nivel."""
    if isinstance(value, dict):
        return {
            key: ("***" if str(key).lower() in _SECRET_KEYS else _redact(item))
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return type(value)(_redact(item) for item in value)
    if isinstance(value, str):
        cleaned = _PATH_PATTERN.sub("[ruta]", value)
        cleaned = _SECRET_PATTERN.sub("***", cleaned)
        return cleaned.replace("Traceback", "[error]")
    return value


class ContextFilter(logging.Filter):
    """Añade contexto de ejecución y redacta claves sensibles."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = getattr(record, "run_id", "-")
        record.case_id = getattr(record, "case_id", "-")
        record.event = getattr(record, "event", "-")
        for key, value in list(record.__dict__.items()):
            if key in _STANDARD_ATTRS:
                continue
            if key in _SECRET_KEYS:
                setattr(record, key, "***")
            else:
                setattr(record, key, _redact(value))
        if isinstance(record.msg, str):
            record.msg = _redact(record.msg)
        if isinstance(record.args, dict):
            record.args = _redact(record.args)
        elif isinstance(record.args, tuple):
            record.args = tuple(_redact(item) for item in record.args)
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
