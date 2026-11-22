"""Criterios del evaluador: un incumplimiento hace fallar el resultado."""

from secguard_advisor.retrieval.evaluation import (
    evaluate_criteria,
    measure_isolation_violations,
)


def _passing(**overrides):
    values = {
        "retrieval_ok": 3,
        "retrieval_total": 3,
        "non_relevant_accepted": 0,
        "isolation_violations": 0,
        "current_only": True,
        "superseded_leaked": False,
        "historical_citation": "valid",
        "qualys_unchanged": True,
    }
    values.update(overrides)
    return evaluate_criteria(**values)


def test_all_criteria_pass() -> None:
    outcome = _passing()

    assert outcome.passed
    assert all(item.passed for item in outcome.criteria)


def test_incomplete_retrieval_fails() -> None:
    outcome = _passing(retrieval_ok=2, retrieval_total=3)

    assert not outcome.passed
    assert not next(c for c in outcome.criteria if c.name == "retrieval").passed


def test_non_relevant_acceptance_fails() -> None:
    outcome = _passing(non_relevant_accepted=1)

    assert not outcome.passed
    assert not next(c for c in outcome.criteria if c.name == "non_relevant").passed


def test_isolation_leak_fails() -> None:
    outcome = _passing(isolation_violations=1)

    assert not outcome.passed
    assert not next(c for c in outcome.criteria if c.name == "isolation").passed


def test_superseded_leak_fails() -> None:
    outcome = _passing(superseded_leaked=True)

    assert not outcome.passed
    assert not next(c for c in outcome.criteria if c.name == "versions").passed


def test_invalid_historical_citation_fails() -> None:
    outcome = _passing(historical_citation="rejected")

    assert not outcome.passed
    assert not next(c for c in outcome.criteria if c.name == "historical_citation").passed


def test_qualys_change_fails() -> None:
    outcome = _passing(qualys_unchanged=False)

    assert not outcome.passed
    assert not next(c for c in outcome.criteria if c.name == "qualys").passed


def test_isolation_measures_private_leaks_and_ignores_public() -> None:
    retrieved = {"a": {"doc-a", "doc-public"}, "b": {"doc-b"}}
    forbidden = {"a": {"doc-b"}, "b": {"doc-a"}}

    assert measure_isolation_violations(retrieved=retrieved, forbidden=forbidden) == 0

    retrieved["a"].add("doc-b")
    assert measure_isolation_violations(retrieved=retrieved, forbidden=forbidden) == 1
