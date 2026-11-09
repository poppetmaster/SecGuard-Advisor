"""Presupuesto de contexto previo a cada generación.

El conteo es una **estimación conservadora**, no un conteo exacto. El tokenizador de
Qwen3.5 no está disponible localmente y los `token_count` medidos al ingerir pertenecen a
EmbeddingGemma. Se usa una cota por bytes UTF-8 con un factor calibrado contra el
generador configurado y un margen de seguridad explícito.
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

# Calibración con `qwen3.5:9b` y el prompt de chat-v2 (español con identificadores
# técnicos): 5689 bytes → 1537 tokens, es decir 3,70 bytes/token. Estimar con 2,4
# bytes/token deja ~54 % de holgura para texto natural y técnico. No es una cota
# matemática: contenido aleatorio o Base64 puede acercarse a 1-2 bytes/token; el
# margen de seguridad y la reducción de fuentes cubren esa frontera.
BYTES_PER_TOKEN = 2.4

# Envoltorio del chat (roles y separadores) y sobrecarga por mensaje o fuente.
CHAT_OVERHEAD_TOKENS = 32
PER_MESSAGE_OVERHEAD = 8


class ContextBudgetExceeded(Exception):
    """El contenido mínimo de la consulta no cabe en el presupuesto."""


@dataclass(frozen=True, slots=True)
class PromptPlan:
    """Prompt listo para enviar, con el contenido que realmente se incluye."""

    system: str
    user: str
    hits: tuple[RetrievedChunk, ...]
    history: tuple[HistoryTurn, ...]
    estimated_prompt_tokens: int
    prompt_limit: int
    output_reserve: int
    safety_margin: int
    dropped_history_messages: int
    dropped_sources: int

    def detail(self) -> dict:
        """Resumen para el paso de ejecución; sin contenido sensible."""
        return {
            "estimated_tokens": self.estimated_prompt_tokens,
            "limit": self.prompt_limit,
            "output_reserve": self.output_reserve,
            "safety_margin": self.safety_margin,
            "history_messages": len(self.history),
            "sources": len(self.hits),
            "dropped_history_messages": self.dropped_history_messages,
            "dropped_sources": self.dropped_sources,
        }


def estimate_tokens(text: str) -> int:
    """Estimación conservadora por bytes UTF-8. No es un conteo exacto."""
    if not text:
        return 0
    return math.ceil(len(text.encode("utf-8")) / BYTES_PER_TOKEN)


def prompt_limit(settings: Settings) -> int:
    """Tokens disponibles para el prompt: contexto menos salida y margen."""
    return (
        settings.generator_num_ctx
        - settings.generator_num_predict
        - settings.context_safety_margin_tokens
    )


def _estimated_prompt_tokens(
    system: str,
    user: str,
    *,
    history_messages: int,
    sources: int,
) -> int:
    return (
        estimate_tokens(system)
        + estimate_tokens(user)
        + CHAT_OVERHEAD_TOKENS
        + PER_MESSAGE_OVERHEAD * (2 + history_messages + sources)
    )


def _drop_oldest_turn(history: list[HistoryTurn]) -> int:
    """Quita el turno más antiguo completo y devuelve cuántos mensajes quitó."""
    if len(history) >= 2 and history[0].role == "user" and history[1].role == "assistant":
        del history[:2]
        return 2
    del history[:1]
    return 1


def plan_prompt(
    *,
    question: str,
    hits: tuple[RetrievedChunk, ...],
    history: tuple[HistoryTurn, ...],
    settings: Settings,
    repair_reasons: list[str] | None = None,
) -> PromptPlan:
    """Construye el prompt y lo reduce hasta caber en el presupuesto.

    Orden de reducción: primero el historial más antiguo (turnos completos) y
    después las fuentes de menor rango. La pregunta actual y los textos de las
    fuentes incluidas nunca se recortan. El historial persistido no se modifica.
    """
    limit = prompt_limit(settings)
    if limit <= 0:
        raise ContextBudgetExceeded(
            "La configuración del generador no deja espacio para el prompt."
        )

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
        estimated = _estimated_prompt_tokens(
            SYSTEM_PROMPT,
            user_prompt,
            history_messages=len(kept_history),
            sources=len(kept_hits),
        )
        if estimated <= limit:
            return PromptPlan(
                system=SYSTEM_PROMPT,
                user=user_prompt,
                hits=tuple(kept_hits),
                history=tuple(kept_history),
                estimated_prompt_tokens=estimated,
                prompt_limit=limit,
                output_reserve=settings.generator_num_predict,
                safety_margin=settings.context_safety_margin_tokens,
                dropped_history_messages=dropped_history,
                dropped_sources=dropped_sources,
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
