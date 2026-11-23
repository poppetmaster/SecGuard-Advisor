"""Cliente de generación local sobre Ollama, sin respaldo automático."""

from __future__ import annotations

import os
import threading
import time
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from typing import Any

import httpx
from langchain_ollama import ChatOllama
from pydantic import BaseModel, ConfigDict, Field


class ModelUnavailable(Exception):
    """Ollama no responde o el modelo no está instalado."""


class ModelTimeout(Exception):
    """Se agotó el tiempo de una llamada al modelo."""


class RunTimeout(Exception):
    """Se agotó el tiempo total del turno."""


class StepLimit(Exception):
    """Se excedió el máximo de operaciones del turno."""


class InvalidModelOutput(Exception):
    """La salida del modelo no cumple el esquema esperado."""

    def __init__(self, message: str, *, reason: str | None = None) -> None:
        super().__init__(message)
        self.reason = reason


class Claim(BaseModel):
    """Afirmación con las fuentes y la cita literal que la sostienen."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(description="Afirmación redactada en español")
    chunk_ids: list[str] = Field(
        default_factory=list,
        description="Identificadores de las fuentes recuperadas que sostienen la afirmación",
    )
    quote: str = Field(
        default="",
        description="Texto copiado literalmente de una de las fuentes, de hasta 400 caracteres",
    )


class ToolArguments(BaseModel):
    """Argumentos estructurados y acotados de findings_query.

    Las claves son estrictas (sin ``case_id`` ni campos extra). La validación de
    valores y rangos se delega a ``FindingsArguments`` para conservar la
    corrección de argumentos inválidos por el modelo.
    """

    model_config = ConfigDict(extra="forbid")

    origin: str | None = Field(default=None, description="Espacio de hallazgos")
    snapshot_id: str | None = Field(default=None, description="Instantánea importada")
    asset: str | None = Field(default=None, description="Activo del caso")
    severity: str | None = Field(default=None, description="Severidad de la escala")
    severity_level: int | None = Field(default=None, description="Nivel de severidad 1-5")
    status_group: str | None = Field(default=None, description="Grupo de estado")
    priority: bool | None = Field(default=None, description="Indicador de prioridad")
    exploitability: str | None = Field(default=None, description="Explotabilidad")
    malware: str | None = Field(default=None, description="Malware")
    qid: str | None = Field(default=None, description="QID de Qualys")
    cve: str | None = Field(default=None, description="CVE")
    group_by: str | None = Field(default=None, description="Agrupación")
    detail: bool | None = Field(default=None, description="Incluir detalle")
    limit: int | None = Field(default=None, description="Límite del detalle")


class ToolDecision(BaseModel):
    """Decisión estructurada del modelo sobre usar findings_query."""

    model_config = ConfigDict(extra="forbid")

    use_findings: bool = Field(
        description="Verdadero si la pregunta necesita datos de hallazgos del caso"
    )
    arguments: ToolArguments = Field(
        default_factory=ToolArguments,
        description="Argumentos estructurados y acotados de findings_query",
    )


class AnswerPayload(BaseModel):
    """Respuesta estructurada del agente documental."""

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(description="Respuesta en español para el usuario")
    claims: list[Claim] = Field(
        default_factory=list, description="Afirmaciones con su respaldo documental"
    )
    missing_info: list[str] = Field(
        default_factory=list, description="Información que falta para responder por completo"
    )
    recommendations: list[str] = Field(
        default_factory=list, description="Recomendaciones derivadas de la evidencia"
    )


class _DeadlineGuard:
    """Reloj monotónico y cierre de la operación al vencer el plazo total."""

    def __init__(self, deadline: float) -> None:
        self.deadline = deadline
        self.expired = threading.Event()
        self._lock = threading.Lock()
        self._response: httpx.Response | None = None
        self._transport: httpx.BaseTransport | None = None
        delay = max(0.0, deadline - time.monotonic())
        self._timer = threading.Timer(delay, self._expire)
        self._timer.daemon = True
        self._timer.start()

    def set_transport(self, transport: httpx.BaseTransport) -> None:
        with self._lock:
            self._transport = transport
        if self.expired.is_set():
            self._close_transport()

    def attach(self, response: httpx.Response) -> None:
        with self._lock:
            self._response = response
        if self.expired.is_set():
            response.close()
            raise TimeoutError("timed out: total model deadline")

    def _close_transport(self) -> None:
        with self._lock:
            transport = self._transport
        if transport is not None:
            with suppress(Exception):
                transport.close()

    def _expire(self) -> None:
        self.expired.set()
        with self._lock:
            response = self._response
        if response is not None:
            with suppress(Exception):
                response.close()
        self._close_transport()

    def finish(self) -> None:
        self._timer.cancel()
        with self._lock:
            self._response = None
            self._transport = None


class _DeadlineStream(httpx.SyncByteStream):
    """Corta la lectura cuando se supera el plazo total, incluso si está bloqueada."""

    def __init__(self, stream: httpx.SyncByteStream, guard: _DeadlineGuard) -> None:
        self._stream = stream
        self._guard = guard

    def __iter__(self):
        try:
            for chunk in self._stream:
                if self._guard.expired.is_set():
                    raise TimeoutError("timed out: total model deadline")
                yield chunk
        except TimeoutError:
            raise
        except (httpx.StreamError, httpx.ReadError, RuntimeError) as exc:
            if self._guard.expired.is_set():
                raise TimeoutError("timed out: total model deadline") from exc
            raise
        if self._guard.expired.is_set():
            raise TimeoutError("timed out: total model deadline")
        self._guard.finish()

    def close(self) -> None:
        try:
            self._stream.close()
        finally:
            self._guard.finish()


class _DeadlineTransport(httpx.BaseTransport):
    """Transporte HTTP que aplica un plazo total a cabeceras y cuerpo."""

    def __init__(self, deadline: float, transport: httpx.BaseTransport | None = None) -> None:
        self._guard = _DeadlineGuard(deadline)
        self._transport = transport or httpx.HTTPTransport()
        self._guard.set_transport(self._transport)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if self._guard.expired.is_set():
            raise TimeoutError("timed out: total model deadline")
        try:
            response = self._transport.handle_request(request)
        except Exception:
            if self._guard.expired.is_set():
                raise TimeoutError("timed out: total model deadline") from None
            raise
        self._guard.attach(response)
        if response.stream is not None:
            response.stream = _DeadlineStream(response.stream, self._guard)
        return response

    def close(self) -> None:
        self._guard.finish()
        self._transport.close()


@dataclass(frozen=True, slots=True)
class GenerationConfig:
    base_url: str
    model: str
    num_ctx: int
    temperature: float
    seed: int
    timeout_seconds: float
    num_predict: int = 1200


@dataclass
class OllamaGenerator:
    """Generador con salida estructurada, semilla fija y sin fallback."""

    config: GenerationConfig
    model: str = field(init=False)
    provider: str = field(init=False, default="ollama")
    digest: str | None = None
    last_usage: dict | None = None

    def __post_init__(self) -> None:
        self.model = self.config.model

    @property
    def identity(self) -> str | None:
        """Digest local observado; no se inventa cuando falta."""
        return self.digest

    def close(self) -> None:
        """Ollama local no mantiene un cliente persistente que cerrar."""
        return None

    def resolve_digest(self) -> str | None:
        """Consulta el digest instalado; si no está disponible, no inventa uno."""
        try:
            response = httpx.get(f"{self.config.base_url.rstrip('/')}/api/tags", timeout=2.0)
            if response.status_code != 200:
                return None
        except Exception:
            return None
        for item in response.json().get("models", []):
            name = item.get("name") or item.get("model") or ""
            if name == self.config.model or name.split(":")[0] == self.config.model.split(":")[0]:
                return item.get("digest")
        return None

    def _chat(self, timeout_seconds: float | None = None) -> ChatOllama:
        effective_timeout = timeout_seconds or self.config.timeout_seconds
        deadline = time.monotonic() + effective_timeout
        return ChatOllama(
            model=self.config.model,
            base_url=self.config.base_url,
            num_ctx=self.config.num_ctx,
            temperature=self.config.temperature,
            seed=self.config.seed,
            num_predict=self.config.num_predict,
            # El modelo configurado es de razonamiento: se desactiva para acotar la
            # latencia y obtener la salida estructurada dentro del presupuesto del turno.
            reasoning=False,
            client_kwargs={
                "timeout": effective_timeout,
                "transport": _DeadlineTransport(deadline),
            },
        )

    def decide(
        self, *, system: str, user: str, timeout_seconds: float | None = None
    ) -> ToolDecision:
        """Pide al modelo la decisión estructurada sobre findings_query."""
        return self._structured(
            system=system,
            user=user,
            schema=ToolDecision,
            timeout_seconds=timeout_seconds,
        )

    def generate(
        self, *, system: str, user: str, timeout_seconds: float | None = None
    ) -> AnswerPayload:
        """Genera la respuesta estructurada o falla con un error clasificado."""
        return self._structured(
            system=system,
            user=user,
            schema=AnswerPayload,
            timeout_seconds=timeout_seconds,
        )

    def _structured(self, *, system: str, user: str, schema, timeout_seconds=None):
        structured = self._chat(timeout_seconds).with_structured_output(
            schema, method="json_schema", include_raw=True
        )
        try:
            with _auto_tracing_disabled():
                result = structured.invoke([("system", system), ("human", user)])
        except (httpx.ConnectError, ConnectionError) as exc:
            raise ModelUnavailable("El modelo local no responde.") from exc
        except (httpx.ReadTimeout, httpx.ConnectTimeout, TimeoutError) as exc:
            raise ModelTimeout("Se agotó el tiempo de espera del modelo.") from exc
        except Exception as exc:
            message = str(exc).lower()
            if "refused" in message or "connect" in message or "not found" in message:
                raise ModelUnavailable("El modelo local no responde.") from exc
            if "timed out" in message or "timeout" in message:
                raise ModelTimeout("Se agotó el tiempo de espera del modelo.") from exc
            raise InvalidModelOutput("La salida del modelo no cumple el esquema esperado.") from exc

        raw = None
        parsed = result
        parse_error = None
        if isinstance(result, dict) and "raw" in result and "parsed" in result:
            raw = result.get("raw")
            parsed = result.get("parsed")
            parse_error = result.get("parsing_error")
        self.last_usage = _usage_of(raw)

        if parse_error is not None:
            raise InvalidModelOutput("La salida del modelo no cumple el esquema esperado.")
        if isinstance(parsed, schema):
            return parsed
        if isinstance(parsed, dict):
            try:
                return schema.model_validate(parsed)
            except Exception as exc:
                raise InvalidModelOutput(
                    "La salida del modelo no cumple el esquema esperado."
                ) from exc
        raise InvalidModelOutput("La salida del modelo no cumple el esquema esperado.")


@contextmanager
def _auto_tracing_disabled():
    """Evita una traza duplicada de LangChain junto con la traza manual.

    La traza del producto se construye explícitamente en ``evidence.tracing``.
    Si el entorno habilita la instrumentación automática de LangChain, se apaga
    solo durante la llamada al modelo y se restaura después.
    """
    keys = ("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2", "LANGCHAIN_TRACING")
    previous = {key: os.environ.get(key) for key in keys}
    for key in keys:
        os.environ[key] = "false"
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _usage_of(raw) -> dict | None:
    """Tokens observados por Ollama, si el mensaje los informa."""
    if raw is None:
        return None
    metadata = getattr(raw, "response_metadata", None) or {}
    prompt_tokens = metadata.get("prompt_eval_count")
    output_tokens = metadata.get("eval_count")
    if prompt_tokens is None:
        usage = getattr(raw, "usage_metadata", None) or {}
        prompt_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
    if prompt_tokens is None:
        return None
    return {
        "prompt_tokens": prompt_tokens,
        "input_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "cached_tokens": None,
        "cache_write_tokens": None,
        "source": "observed",
    }


@dataclass(frozen=True, slots=True)
class TimedStep:
    """Paso de la ejecución con su duración observada."""

    name: str
    origin: str
    status: str
    duration_ms: int
    detail: dict[str, Any] | None = None


def elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
