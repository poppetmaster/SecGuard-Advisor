"""Presupuesto de contexto previo a cada generación.

La **admisión** usa el tokenizador del propio generador (vocabulario y fusiones BPE
del GGUF instalado) y su plantilla de conversación: no es una estimación por bytes.
`estimate_tokens` queda solo como diagnóstico y nunca decide si una llamada cabe.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from secguard_advisor.config import Settings
from secguard_advisor.conversation.memory import HistoryTurn
from secguard_advisor.conversation.prompts import (
    SYSTEM_PROMPT,
    build_repair_prompt,
    build_user_prompt,
)
from secguard_advisor.retrieval.search import RetrievedChunk


class ContextBudgetExceeded(Exception):
    """El contenido mínimo de la consulta no cabe en el presupuesto."""


class ContextBudgetUnavailable(RuntimeError):
    """No se pudo cargar el tokenizador del generador para admitir la llamada."""


# Diagnóstico: bytes UTF-8 por token observados con qwen3.5:9b en español técnico
# (3,7-3,8). No se usa para admitir porque hay entradas con menos bytes por token.
DIAGNOSTIC_BYTES_PER_TOKEN = 2.4


@dataclass(frozen=True, slots=True)
class PromptPlan:
    """Prompt listo para enviar, con el contenido que realmente se incluye."""

    system: str
    user: str
    hits: tuple[RetrievedChunk, ...]
    history: tuple[HistoryTurn, ...]
    admitted_tokens: int
    estimated_tokens: int
    prompt_limit: int
    output_reserve: int
    safety_margin: int
    dropped_history_messages: int
    dropped_sources: int
    counter: dict

    def detail(self) -> dict:
        """Resumen para el paso de ejecución; sin contenido sensible."""
        return {
            "admitted_tokens": self.admitted_tokens,
            "estimated_tokens": self.estimated_tokens,
            "limit": self.prompt_limit,
            "output_reserve": self.output_reserve,
            "safety_margin": self.safety_margin,
            "history_messages": len(self.history),
            "sources": len(self.hits),
            "dropped_history_messages": self.dropped_history_messages,
            "dropped_sources": self.dropped_sources,
            "counter": self.counter,
        }


def estimate_tokens(text: str) -> int:
    """Estimación por bytes; solo diagnóstico, no control de admisión."""
    if not text:
        return 0
    return math.ceil(len(text.encode("utf-8")) / DIAGNOSTIC_BYTES_PER_TOKEN)


def prompt_limit(settings: Settings) -> int:
    """Tokens disponibles para el prompt: contexto menos salida y margen."""
    return (
        settings.generator_num_ctx
        - settings.generator_num_predict
        - settings.context_safety_margin_tokens
    )


def _drop_oldest_turn(history: list[HistoryTurn]) -> int:
    """Quita el turno más antiguo completo y devuelve cuántos mensajes quitó."""
    if len(history) >= 2 and history[0].role == "user" and history[1].role == "assistant":
        del history[:2]
        return 2
    del history[:1]
    return 1


def _diagnostic_estimate(system: str, user: str) -> int:
    return estimate_tokens(system) + estimate_tokens(user)


def plan_prompt(
    *,
    question: str,
    hits: tuple[RetrievedChunk, ...],
    history: tuple[HistoryTurn, ...],
    settings: Settings,
    counter,
    repair_reasons: list[str] | None = None,
) -> PromptPlan:
    """Construye el prompt y lo reduce hasta que el tokenizador lo admita.

    Orden de reducción: primero el historial más antiguo (turnos completos) y
    después las fuentes de menor rango. La pregunta actual y los textos de las
    fuentes incluidas nunca se recortan. El historial persistido no se modifica.
    """
    limit = prompt_limit(settings)
    if limit <= 0:
        raise ContextBudgetExceeded(
            "La configuración del generador no deja espacio para el prompt."
        )

    try:
        counter.count(SYSTEM_PROMPT, "")
    except Exception as exc:
        raise ContextBudgetUnavailable(
            "No se pudo cargar el tokenizador del generador para medir el prompt."
        ) from exc

    kept_history = list(history)
    kept_hits = list(hits)
    dropped_history = 0
    dropped_sources = 0

    while True:
        if repair_reasons is None:
            user_prompt = build_user_prompt(question, tuple(kept_hits), tuple(kept_history))
        else:
            user_prompt = build_repair_prompt(
                question, tuple(kept_hits), repair_reasons, tuple(kept_history)
            )
        try:
            admitted = counter.count(SYSTEM_PROMPT, user_prompt)
        except Exception as exc:
            raise ContextBudgetUnavailable(
                "No se pudo cargar el tokenizador del generador para medir el prompt."
            ) from exc
        if admitted <= limit:
            return PromptPlan(
                system=SYSTEM_PROMPT,
                user=user_prompt,
                hits=tuple(kept_hits),
                history=tuple(kept_history),
                admitted_tokens=admitted,
                estimated_tokens=_diagnostic_estimate(SYSTEM_PROMPT, user_prompt),
                prompt_limit=limit,
                output_reserve=settings.generator_num_predict,
                safety_margin=settings.context_safety_margin_tokens,
                dropped_history_messages=dropped_history,
                dropped_sources=dropped_sources,
                counter=counter.describe(),
            )
        if kept_history:
            dropped_history += _drop_oldest_turn(kept_history)
            continue
        if len(kept_hits) > 1:
            kept_hits.pop()
            dropped_sources += 1
            continue
        raise ContextBudgetExceeded(
            "La consulta excede el presupuesto de contexto incluso con el contenido mínimo."
        )
