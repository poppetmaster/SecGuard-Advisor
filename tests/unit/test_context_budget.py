"""Pruebas del presupuesto de contexto previo a la generación.

La admisión usa el tokenizador del generador; en estas pruebas con dobles se usa
`FakeTokenCounter`, que solo imita la interfaz. La exactitud del tokenizador se
comprueba en `tests/integration/test_context_budget_real.py`.
"""

from __future__ import annotations

import pytest
from tests.fixtures.fakes import FakeTokenCounter

from secguard_advisor.config import Settings
from secguard_advisor.conversation.budget import (
    DIAGNOSTIC_BYTES_PER_TOKEN,
    ContextBudgetExceeded,
    estimate_tokens,
    plan_prompt,
    prompt_limit,
)
from secguard_advisor.conversation.memory import HistoryTurn
from secguard_advisor.conversation.prompts import SYSTEM_PROMPT
from secguard_advisor.retrieval.search import RetrievedChunk

COUNTER = FakeTokenCounter()


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def _hit(index: int, text: str = "texto de la fuente") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=f"{index:032x}",
        document_id="d" * 32,
        version_id="v" * 32,
        document_title=f"Documento {index}",
        declared_version="v1",
        origin="public_corpus",
        page=index,
        section=None,
        locator=f"p:{index}#0",
        text=text,
        score=1.0 - index / 100,
        version_current=True,
        token_count=10,
    )


def _history(pairs: int, size: int = 100) -> tuple[HistoryTurn, ...]:
    turns: list[HistoryTurn] = []
    seq = 1
    for index in range(1, pairs + 1):
        turns.append(HistoryTurn(seq, "user", f"pregunta {index} " + "q" * size))
        seq += 1
        turns.append(HistoryTurn(seq, "assistant", f"respuesta {index} " + "a" * size))
        seq += 1
    return tuple(turns)


def test_estimate_is_diagnostic_and_not_used_for_admission() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("a" * 240) == 100
    assert estimate_tokens("ñ" * 10) > estimate_tokens("n" * 10)
    assert estimate_tokens("漢" * 10) > 10
    assert DIAGNOSTIC_BYTES_PER_TOKEN == 2.4
    plan = plan_prompt(question="¿Qué?", hits=(), history=(), settings=_settings(), counter=COUNTER)
    assert plan.counter["method"] == "fake"
    assert plan.admitted_tokens <= plan.prompt_limit


def test_plan_keeps_everything_when_it_fits() -> None:
    settings = _settings()
    history = _history(2)
    hits = (_hit(1), _hit(2))

    plan = plan_prompt(
        question="¿Qué funciones define?",
        hits=hits,
        history=history,
        settings=settings,
        counter=COUNTER,
    )

    assert plan.history == history
    assert plan.hits == hits
    assert plan.dropped_history_messages == 0
    assert plan.dropped_sources == 0
    assert plan.admitted_tokens <= plan.prompt_limit
    assert plan.prompt_limit == prompt_limit(settings)


def test_history_is_reduced_oldest_first_with_whole_turns() -> None:
    settings = _settings(generator_num_ctx=5000)
    history = _history(5, size=1500)
    hits = (_hit(1, "fuente corta"),)

    plan = plan_prompt(
        question="¿De qué hablamos?",
        hits=hits,
        history=history,
        settings=settings,
        counter=COUNTER,
    )

    assert plan.dropped_history_messages > 0
    assert plan.dropped_sources == 0
    assert len(plan.history) < len(history)
    assert plan.history == history[-len(plan.history) :]
    assert plan.history[0].role == "user"
    assert [turn.role for turn in plan.history] == ["user", "assistant"] * (len(plan.history) // 2)
    assert plan.dropped_history_messages == len(history) - len(plan.history)
    assert plan.dropped_history_messages % 2 == 0
    assert "¿De qué hablamos?" in plan.user


def test_sources_are_reduced_after_history_by_rank() -> None:
    settings = _settings(generator_num_ctx=5000)
    history = _history(2, size=1500)
    hits = tuple(_hit(index, "texto " + "f" * 3000) for index in range(1, 5))

    plan = plan_prompt(
        question="¿Qué dice la evidencia?",
        hits=hits,
        history=history,
        settings=settings,
        counter=COUNTER,
    )

    assert plan.dropped_history_messages == len(history)
    assert plan.dropped_sources > 0
    assert len(plan.hits) >= 1
    assert plan.hits == hits[: len(plan.hits)]
    assert f"[S{len(plan.hits)}]" in plan.user
    assert f"[S{len(plan.hits) + 1}]" not in plan.user
    assert plan.admitted_tokens <= plan.prompt_limit


def test_repair_plan_also_respects_the_budget() -> None:
    settings = _settings(generator_num_ctx=5000)
    hits = tuple(_hit(index, "texto " + "f" * 3000) for index in range(1, 5))

    plan = plan_prompt(
        question="¿Qué dice la evidencia?",
        hits=hits,
        history=_history(3, size=1500),
        settings=settings,
        counter=COUNTER,
        repair_reasons=["quote_not_found"],
    )

    assert "no superó el control automático" in plan.user
    assert plan.admitted_tokens <= plan.prompt_limit
    assert plan.dropped_sources > 0


def test_question_and_source_text_are_not_truncated() -> None:
    settings = _settings()
    question = "¿" + "pregunta larga " * 20 + "?"
    source_text = "contenido íntegro de la fuente " * 10
    hits = (_hit(1, source_text),)

    plan = plan_prompt(
        question=question,
        hits=hits,
        history=_history(1),
        settings=settings,
        counter=COUNTER,
    )

    assert question in plan.user
    assert source_text in plan.user


def test_minimal_content_that_does_not_fit_is_reported() -> None:
    settings = _settings(generator_num_ctx=900, generator_num_predict=1200)

    with pytest.raises(ContextBudgetExceeded):
        plan_prompt(question="¿Cabe?", hits=(), history=(), settings=settings, counter=COUNTER)


def test_oversized_question_is_reported_without_calling_the_model() -> None:
    settings = _settings(generator_num_ctx=2200)
    question = "¿" + "x" * 20_000 + "?"

    with pytest.raises(ContextBudgetExceeded):
        plan_prompt(
            question=question,
            hits=(_hit(1),),
            history=(),
            settings=settings,
            counter=COUNTER,
        )


def test_planning_does_not_mutate_the_received_history_or_sources() -> None:
    settings = _settings(generator_num_ctx=5000)
    history = _history(3, size=1500)
    hits = tuple(_hit(index, "texto " + "f" * 3000) for index in range(1, 4))

    plan = plan_prompt(
        question="¿Qué dice la evidencia?",
        hits=hits,
        history=history,
        settings=settings,
        counter=COUNTER,
    )

    assert len(history) == 6
    assert history[0].content.startswith("pregunta 1")
    assert len(hits) == 3
    assert hits[0].chunk_id == "0" * 31 + "1"
    assert len(plan.history) <= len(history)
    assert len(plan.hits) <= len(hits)


def test_admitted_count_covers_the_system_prompt() -> None:
    plan = plan_prompt(
        question="¿Qué?",
        hits=(),
        history=(),
        settings=_settings(),
        counter=COUNTER,
    )

    assert plan.admitted_tokens >= estimate_tokens(SYSTEM_PROMPT)
    assert plan.admitted_tokens <= plan.prompt_limit


class _UnavailableCounter:
    def count(self, system: str, user: str) -> int:
        raise RuntimeError("tokenizador ausente")

    def describe(self) -> dict:
        return {"method": "unavailable"}


def test_unavailable_tokenizer_is_reported_instead_of_guessing() -> None:
    from secguard_advisor.conversation.budget import ContextBudgetUnavailable

    with pytest.raises(ContextBudgetUnavailable):
        plan_prompt(
            question="¿Qué?",
            hits=(),
            history=(),
            settings=_settings(),
            counter=_UnavailableCounter(),
        )
