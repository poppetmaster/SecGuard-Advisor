"""Redacción centralizada de secretos, rutas y cabeceras."""

from __future__ import annotations

import re
from typing import Any

SECRET_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "x-api-key",
        "deepseek_api_key",
        "anthropic_api_key",
        "langsmith_api_key",
        "password",
        "secret",
        "token",
    }
)
PATH_PATTERN = re.compile(r"(?:/(?:Users|home|private|tmp|var)/[^\s\"']+)")
SECRET_PATTERN = re.compile(r"\b(?:sk-ant-|sk-|lsv2_)[A-Za-z0-9_-]{8,}\b")


def redact_text(value: str) -> str:
    cleaned = PATH_PATTERN.sub("[ruta]", value)
    cleaned = SECRET_PATTERN.sub("***", cleaned)
    return cleaned.replace("Traceback", "[error]")


def redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: ("***" if str(key).lower() in SECRET_KEYS else redact_value(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_value(item) for item in value)
    if isinstance(value, str):
        return redact_text(value)
    return value
