"""Utilidades compartidas de transporte HTTP para proveedores externos."""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from secguard_advisor.conversation.llm import (
    InvalidModelOutput,
    ModelTimeout,
    ModelUnavailable,
)
from secguard_advisor.conversation.providers.base import (
    ProviderAuthError,
    ProviderError,
    ProviderRateLimited,
)


def schema_instruction(system: str, schema) -> str:
    """Añade el esquema JSON al system prompt; DeepSeek exige la palabra JSON."""
    return (
        f"{system}\n\n"
        "Responde únicamente con un objeto JSON válido que cumpla este esquema. "
        "No agregues texto fuera del JSON.\n"
        f"{json.dumps(schema.model_json_schema(), ensure_ascii=False)}"
    )


def parse_structured(content: str, schema):
    if not content or not content.strip():
        raise InvalidModelOutput("La salida del proveedor está vacía.")
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise InvalidModelOutput("La salida del proveedor no es JSON válido.") from exc
    try:
        return schema.model_validate(payload)
    except Exception as exc:
        raise InvalidModelOutput("La salida del proveedor no cumple el esquema.") from exc


def raise_for_status(response: httpx.Response) -> None:
    status = response.status_code
    if status in {401, 403}:
        raise ProviderAuthError("El proveedor rechazó la credencial.")
    if status == 429:
        raise ProviderRateLimited("El proveedor limitó la tasa de solicitudes.")
    if status in {400, 404, 409, 422}:
        raise ProviderError("El proveedor rechazó la solicitud.")
    if status >= 500:
        raise ModelUnavailable("El proveedor no está disponible.")
    if status >= 400:
        raise ProviderError("El proveedor devolvió un error.")


def post_json(
    client: httpx.Client,
    url: str,
    *,
    headers: dict,
    payload: dict,
    timeout_seconds: float | None = None,
) -> dict:
    request_kwargs = {"headers": headers, "json": payload}
    if timeout_seconds is not None:
        request_kwargs["timeout"] = timeout_seconds
    try:
        response = client.post(url, **request_kwargs)
    except (httpx.ReadTimeout, httpx.ConnectTimeout, TimeoutError) as exc:
        raise ModelTimeout("Se agotó el tiempo de espera del proveedor.") from exc
    except (httpx.ConnectError, ConnectionError) as exc:
        raise ModelUnavailable("El proveedor no responde.") from exc
    except httpx.HTTPError as exc:
        raise ProviderError("No se pudo completar la solicitud al proveedor.") from exc
    raise_for_status(response)
    try:
        return response.json()
    except ValueError as exc:
        raise InvalidModelOutput("El proveedor devolvió una respuesta ilegible.") from exc


def usage_dict(
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    cached_tokens: int | None,
    cache_write_tokens: int | None,
    started: float,
) -> dict[str, Any]:
    source = "observed" if input_tokens is not None and output_tokens is not None else "unknown"
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_tokens": cached_tokens,
        "cache_write_tokens": cache_write_tokens,
        "source": source,
        "duration_ms": int((time.perf_counter() - started) * 1000),
    }
