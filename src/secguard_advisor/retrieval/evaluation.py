"""Criterios de evaluación funcional de la recuperación."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Criterion:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class EvaluationOutcome:
    passed: bool
    criteria: tuple[Criterion, ...]


def measure_isolation_violations(
    *,
    retrieved: dict[str, set[str]],
    forbidden: dict[str, set[str]],
) -> int:
    """Cuenta documentos privados recuperados fuera de su caso.

    Los documentos públicos no se incluyen en `forbidden`, por lo que no se
    contabilizan como fuga.
    """
    return sum(
        len(documents & forbidden.get(case_id, set())) for case_id, documents in retrieved.items()
    )


def evaluate_criteria(
    *,
    retrieval_ok: int,
    retrieval_total: int,
    non_relevant_accepted: int,
    isolation_violations: int,
    current_only: bool,
    superseded_leaked: bool,
    historical_citation: str,
    qualys_unchanged: bool,
) -> EvaluationOutcome:
    criteria = (
        Criterion(
            "retrieval",
            retrieval_total > 0 and retrieval_ok == retrieval_total,
            f"{retrieval_ok}/{retrieval_total} consultas pertinentes recuperadas",
        ),
        Criterion(
            "non_relevant",
            non_relevant_accepted == 0,
            f"{non_relevant_accepted} consultas no pertinentes aceptadas",
        ),
        Criterion(
            "isolation",
            isolation_violations == 0,
            f"{isolation_violations} documentos privados cruzados",
        ),
        Criterion(
            "versions",
            current_only and not superseded_leaked,
            f"vigente={current_only}; superada_filtrada={not superseded_leaked}",
        ),
        Criterion(
            "historical_citation",
            historical_citation == "valid",
            f"estado={historical_citation}",
        ),
        Criterion(
            "qualys",
            qualys_unchanged,
            f"sin cambios={qualys_unchanged}",
        ),
    )
    return EvaluationOutcome(passed=all(item.passed for item in criteria), criteria=criteria)
