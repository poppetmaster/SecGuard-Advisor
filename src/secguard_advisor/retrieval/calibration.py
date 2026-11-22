"""Calibración del umbral de recuperación para Qdrant.

Criterios fijados antes de medir:
- una consulta pertinente debe recuperar su fragmento esperado con score >= umbral;
- ninguna consulta fuera de dominio debe superar el umbral;
- se elige el mayor umbral que cumple ambos; si no existe, se registra el fallo y
  se informa el mejor equilibrio observado.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ThresholdChoice:
    threshold: float
    satisfied: bool
    relevant_min: float | None
    non_relevant_max: float | None
    missed_relevant: int
    accepted_non_relevant: int


def choose_threshold(
    relevant_scores: list[float],
    non_relevant_scores: list[float],
) -> ThresholdChoice:
    candidates = sorted({*relevant_scores, *non_relevant_scores})
    if not candidates:
        return ThresholdChoice(0.0, False, None, None, 0, 0)

    def missed(value: float) -> int:
        return sum(1 for score in relevant_scores if score < value)

    def accepted(value: float) -> int:
        return sum(1 for score in non_relevant_scores if score >= value)

    valid = [value for value in candidates if missed(value) == 0 and accepted(value) == 0]
    chosen = (
        max(valid)
        if valid
        else max(
            candidates,
            key=lambda value: (len(relevant_scores) - missed(value) - accepted(value), value),
        )
    )
    return ThresholdChoice(
        threshold=round(chosen, 4),
        satisfied=bool(valid),
        relevant_min=min(relevant_scores) if relevant_scores else None,
        non_relevant_max=max(non_relevant_scores) if non_relevant_scores else None,
        missed_relevant=missed(chosen),
        accepted_non_relevant=accepted(chosen),
    )
