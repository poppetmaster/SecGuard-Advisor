"""Cliente de generación local sobre Ollama, sin respaldo automático."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field


class ModelUnavailable(Exception):
    """Ollama no responde o el modelo no está instalado."""


class ModelTimeout(Exception):
    """Se agotó el tiempo de una llamada al modelo."""


class RunTimeout(Exception):
    """Se agotó el tiempo total del turno."""


class InvalidModelOutput(Exception):
    """La salida del modelo no cumple el esquema esperado."""


class Claim(BaseModel):
    """Afirmación con las fuentes y la cita literal que la sostienen."""

    text: str = Field(description="Afirmación redactada en español")
    chunk_ids: list[str] = Field(
        default_factory=list,
        description="Identificadores de las fuentes recuperadas que sostienen la afirmación",
    )
    quote: str = Field(
        default="",
        description="Texto copiado literalmente de una de las fuentes, de hasta 400 caracteres",
    )


class ToolDecision(BaseModel):
    """Decisión estructurada del modelo sobre usar findings_query."""

    use_findings: bool = Field(
        description="Verdadero si la pregunta necesita datos de hallazgos del caso"
    )
    arguments: dict = Field(default_factory=dict, description="Argumentos de findings_query")


class AnswerPayload(BaseModel):
    """Respuesta estructurada del agente documental."""

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
    digest: str | None = None
    last_usage: dict | None = None

    def __post_init__(self) -> None:
        self.model = self.config.model

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

    def _chat(self) -> ChatOllama:
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
            client_kwargs={"timeout": self.config.timeout_seconds},
        )

    def decide(self, *, system: str, user: str) -> ToolDecision:
        """Pide al modelo la decisión estructurada sobre findings_query."""
        return self._structured(system=system, user=user, schema=ToolDecision)

    def generate(self, *, system: str, user: str) -> AnswerPayload:
        """Genera la respuesta estructurada o falla con un error clasificado."""
        return self._structured(system=system, user=user, schema=AnswerPayload)

    def _structured(self, *, system: str, user: str, schema):
        structured = self._chat().with_structured_output(
            schema, method="json_schema", include_raw=True
        )
        try:
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
    return {"prompt_tokens": prompt_tokens, "output_tokens": output_tokens}


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
