"""Traza externa acotada y correlacionable con la ejecución local.

La aplicación nunca escribe ``confirmed``: como máximo ``submitted`` tras un
``flush`` sin error observado. La confirmación corresponde a la aceptación
(T091). El contenido enviado se limita a metadatos: no incluye la pregunta,
prompts, documentos del caso, argumentos de herramienta ni rutas locales.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from secguard_advisor.config import Settings

_SECRET_KEYS = frozenset({"api_key", "authorization", "password", "secret", "token"})
_PATH_PATTERN = re.compile(r"(?:/(?:Users|home|private|tmp|var)/[^\s\"']+)")
_SECRET_PATTERN = re.compile(r"\b(?:lsv2_|sk-)[A-Za-z0-9_-]{8,}\b")
_FLUSH_TIMEOUT_SECONDS = 5.0
_CLIENT_TIMEOUT_MS = 3000


@dataclass(frozen=True, slots=True)
class TraceOutcome:
    """Resultado observable del envío de la traza."""

    status: str
    trace_id: str | None = None
    trace_url: str | None = None
    error: str | None = None


def _scrub(value: Any) -> Any:
    """Elimina secretos, rutas absolutas y trazas de pila de un payload."""
    if isinstance(value, dict):
        return {
            key: ("***" if str(key).lower() in _SECRET_KEYS else _scrub(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    if isinstance(value, tuple):
        return [_scrub(item) for item in value]
    if isinstance(value, str):
        cleaned = _PATH_PATTERN.sub("[ruta]", value)
        cleaned = _SECRET_PATTERN.sub("***", cleaned)
        return cleaned.replace("Traceback", "[error]")
    return value


class NullTracer:
    """Traza desactivada: no crea clientes ni realiza envíos."""

    def start(self, **_kwargs) -> None:
        return None

    def operation(self, _name: str, **_kwargs) -> None:
        return None

    def finish(self, **_kwargs) -> TraceOutcome:
        return TraceOutcome("disabled")


class LangSmithTracer:
    """Envía una traza raíz y sus operaciones relevantes a LangSmith."""

    def __init__(
        self,
        settings: Settings,
        *,
        client_factory=None,
        run_tree_factory=None,
    ) -> None:
        self._settings = settings
        self._client_factory = client_factory or _default_client
        self._run_tree_factory = run_tree_factory or _default_run_tree
        self._client = None
        self._root = None
        self._failed = False

    def start(
        self,
        *,
        run_id: str,
        case_id: str,
        attempt_no: int,
        prompt_version: str,
        question_length: int | None = None,
        metadata: dict | None = None,
    ) -> None:
        api_key = self._settings.langsmith_api_key
        if api_key is None:
            self._failed = True
            return
        try:
            self._client = self._client_factory(
                api_url=self._settings.langsmith_endpoint,
                api_key=api_key.get_secret_value(),
                timeout_ms=_CLIENT_TIMEOUT_MS,
            )
            run_metadata = {
                "component": "secguard-advisor",
                "prompt_version": prompt_version,
                "app_version": self._settings.app_version,
                "app_env": self._settings.app_env,
                "generator_model": self._settings.ollama_model,
                "embedding_model": self._settings.ollama_embedding_model,
                "embedding_dim": self._settings.embedding_dim,
                "num_ctx": self._settings.generator_num_ctx,
                "num_predict": self._settings.generator_num_predict,
                "temperature": self._settings.generator_temperature,
                "seed": self._settings.generator_seed,
                "max_tool_calls": self._settings.max_tool_calls,
                "max_graph_steps": self._settings.max_graph_steps,
                "run_timeout_seconds": self._settings.run_timeout_seconds,
                "llm_timeout_seconds": self._settings.llm_timeout_seconds,
                "retrieval_top_k": self._settings.retrieval_top_k,
                "retrieval_min_score": self._settings.retrieval_min_score,
                "retrieval_token_budget": self._settings.retrieval_token_budget,
                "history_max_messages": self._settings.history_max_messages,
                "history_max_chars": self._settings.history_max_chars,
            }
            run_metadata.update(metadata or {})
            run_metadata = {key: value for key, value in run_metadata.items() if value is not None}
            run_inputs = {
                "run_id": run_id,
                "case_id": case_id,
                "attempt_no": attempt_no,
                "prompt_version": prompt_version,
            }
            if question_length is not None:
                run_inputs["question_length"] = question_length
            self._root = self._run_tree_factory(
                name="secguard-advisor.turn",
                run_type="chain",
                inputs=run_inputs,
                ls_client=self._client,
                project_name=self._settings.langsmith_project,
                tags=["secguard-advisor", f"env:{self._settings.app_env}"],
                extra={"metadata": _scrub(run_metadata)},
            )
            self._root.post()
        except Exception:
            self._failed = True
            self._root = None

    def operation(
        self,
        name: str,
        *,
        run_type: str,
        inputs: dict | None = None,
        outputs: dict | None = None,
        error: str | None = None,
        duration_ms: int | None = None,
    ) -> None:
        if self._failed or self._root is None:
            return
        try:
            child = self._root.create_child(
                name=name,
                run_type=run_type,
                inputs=_scrub(inputs or {}),
            )
            child.post()
            payload = dict(outputs or {})
            if duration_ms is not None:
                payload["duration_ms"] = duration_ms
            child.end(outputs=_scrub(payload), error=_scrub(error))
            child.patch()
        except Exception:
            self._failed = True

    def finish(
        self, *, status: str, outcome: str | None, duration_ms: int | None = None
    ) -> TraceOutcome:
        if self._failed or self._root is None:
            return TraceOutcome("failed", error="trace_send_failed")
        try:
            outputs = {"status": status, "outcome": outcome}
            if duration_ms is not None:
                outputs["duration_ms"] = duration_ms
            self._root.end(outputs=_scrub(outputs))
            self._root.patch()
            self._client.flush(timeout=_FLUSH_TIMEOUT_SECONDS)
            trace_id = str(getattr(self._root, "id", "") or "") or None
            try:
                trace_url = self._root.get_url()
            except Exception:
                trace_url = None
            return TraceOutcome("submitted", trace_id=trace_id, trace_url=trace_url)
        except Exception:
            trace_id = str(getattr(self._root, "id", "") or "") or None
            return TraceOutcome("failed", trace_id=trace_id, error="trace_send_failed")


def _default_client(*, api_url: str, api_key: str, timeout_ms: int):
    from langsmith import Client

    return Client(
        api_url=api_url,
        api_key=api_key,
        timeout_ms=timeout_ms,
        # Envío síncrono para observar el error y no marcar submitted a ciegas.
        auto_batch_tracing=False,
    )


def _default_run_tree(**kwargs):
    from langsmith.run_trees import RunTree

    return RunTree(**kwargs)


def build_tracer(settings: Settings):
    """Devuelve una traza real solo con interruptor y credenciales presentes."""
    if not settings.langsmith_tracing or settings.langsmith_api_key is None:
        return NullTracer()
    return LangSmithTracer(settings)
