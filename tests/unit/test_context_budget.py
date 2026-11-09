"""Pruebas del presupuesto de contexto previo a la generación."""

from __future__ import annotations

import pytest

from secguard_advisor.config import Settings
from secguard_advisor.conversation.budget import (
    BYTES_PER_TOKEN,
    CHAT_OVERHEAD_TOKENS,
    PER_MESSAGE_OVERHEAD,
    ContextBudgetExceeded,
    estimate_tokens,
    plan_prompt,
    prompt_limit,
)
from secguard_advisor.conversation.memory import HistoryTurn
from secguard_advisor.conversation.prompts import SYSTEM_PROMPT
from secguard_advisor.retrieval.search import RetrievedChunk


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


def test_estimate_is_byte_based_and_not_a_char_count() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("a" * 240) == 100
    assert estimate_tokens("ñ" * 10) > estimate_tokens("n" * 10)
    assert estimate_tokens("漢" * 10) > 10
    assert BYTES_PER_TOKEN == 2.4


def test_plan_keeps_everything_when_it_fits() -> None:
    settings = _settings()
    history = _history(2)
    hits = (_hit(1), _hit(2))

    plan = plan_prompt(
        question="¿Qué funciones define?",
        hits=hits,
        history=history,
        settings=settings,
    )

    assert plan.history == history
    assert plan.hits == hits
    assert plan.dropped_history_messages == 0
    assert plan.dropped_sources == 0
    assert plan.estimated_prompt_tokens <= plan.prompt_limit
    assert plan.prompt_limit == prompt_limit(settings)


def test_history_is_reduced_oldest_first_with_whole_turns() -> None:
    settings = _settings(generator_num_ctx=4200)
    history = _history(5, size=1500)
    hits = (_hit(1, "fuente corta"),)

    plan = plan_prompt(
        question="¿De qué hablamos?",
        hits=hits,
        history=history,
        settings=settings,
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
    settings = _settings(generator_num_ctx=4200)
    history = _history(2, size=1500)
    hits = tuple(_hit(index, "texto " + "f" * 3000) for index in range(1, 5))

    plan = plan_prompt(
        question="¿Qué dice la evidencia?",
        hits=hits,
        history=history,
        settings=settings,
    )

    assert plan.dropped_history_messages == len(history)
    assert plan.dropped_sources > 0
    assert len(plan.hits) >= 1
    assert plan.hits == hits[: len(plan.hits)]
    assert f"[S{len(plan.hits)}]" in plan.user
    assert f"[S{len(plan.hits) + 1}]" not in plan.user
    assert plan.estimated_prompt_tokens <= plan.prompt_limit


def test_repair_plan_also_respects_the_budget() -> None:
    settings = _settings(generator_num_ctx=4200)
    hits = tuple(_hit(index, "texto " + "f" * 3000) for index in range(1, 5))

    plan = plan_prompt(
        question="¿Qué dice la evidencia?",
        hits=hits,
        history=_history(3, size=1500),
        settings=settings,
        repair_reasons=["quote_not_found"],
    )

    assert "no superó el control automático" in plan.user
    assert plan.estimated_prompt_tokens <= plan.prompt_limit
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
    )

    assert question in plan.user
    assert source_text in plan.user


def test_minimal_content_that_does_not_fit_is_reported() -> None:
    settings = _settings(generator_num_ctx=900, generator_num_predict=1200)

    with pytest.raises(ContextBudgetExceeded):
        plan_prompt(question="¿Cabe?", hits=(), history=(), settings=settings)


def test_oversized_question_is_reported_without_calling_the_model() -> None:
    settings = _settings(generator_num_ctx=2200)
    question = "¿" + "x" * 20_000 + "?"

    with pytest.raises(ContextBudgetExceeded):
        plan_prompt(question=question, hits=(_hit(1),), history=(), settings=settings)


def test_planning_does_not_mutate_the_received_history_or_sources() -> None:
    settings = _settings(generator_num_ctx=4200)
    history = _history(3, size=1500)
    hits = tuple(_hit(index, "texto " + "f" * 3000) for index in range(1, 4))

    plan = plan_prompt(
        question="¿Qué dice la evidencia?",
        hits=hits,
        history=history,
        settings=settings,
    )

    assert len(history) == 6
    assert history[0].content.startswith("pregunta 1")
    assert len(hits) == 3
    assert hits[0].chunk_id == "0" * 31 + "1"
    assert len(plan.history) <= len(history)
    assert len(plan.hits) <= len(hits)


def test_estimate_includes_system_prompt_and_overhead() -> None:
    settings = _settings()
    plan = plan_prompt(question="¿Qué?", hits=(), history=(), settings=settings)
    expected_minimum = estimate_tokens(SYSTEM_PROMPT) + CHAT_OVERHEAD_TOKENS

    assert plan.estimated_prompt_tokens >= expected_minimum
    assert plan.estimated_prompt_tokens <= plan.prompt_limit
    assert PER_MESSAGE_OVERHEAD >= 1
