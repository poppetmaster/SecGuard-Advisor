"""Grafo del turno documental: recuperar, generar, validar y persistir."""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from secguard_advisor.conversation.nodes import (
    abstain,
    agent,
    load_scope,
    persist,
    repair,
    retrieve,
    route_after_validate,
    validate,
)


class TurnState(TypedDict, total=False):
    """Estado interno del turno; no se serializa ni se guarda como memoria."""

    context: Any
    hits: tuple
    retrieval_status: str
    payload: Any
    citations: tuple
    rejected: tuple
    answer: str
    outcome: str
    repaired: bool
    steps: tuple
    answer_message_id: str
    persisted: bool


def build_turn_graph():
    """Compone el grafo con una única reparación de citas."""
    builder = StateGraph(TurnState)
    builder.add_node("load_scope", load_scope)
    builder.add_node("retrieve", retrieve)
    builder.add_node("agent", agent)
    builder.add_node("validate", validate)
    builder.add_node("repair", repair)
    builder.add_node("abstain", abstain)
    builder.add_node("persist", persist)

    builder.add_edge(START, "load_scope")
    builder.add_edge("load_scope", "retrieve")
    builder.add_edge("retrieve", "agent")
    builder.add_edge("agent", "validate")
    builder.add_conditional_edges(
        "validate",
        route_after_validate,
        {"persist": "persist", "repair": "repair", "abstain": "abstain"},
    )
    builder.add_edge("repair", "validate")
    builder.add_edge("abstain", "persist")
    builder.add_edge("persist", END)
    return builder.compile()


TURN_GRAPH = build_turn_graph()


def run_turn_graph(context) -> dict[str, Any]:
    """Ejecuta el turno completo desde el estado inicial."""
    initial: TurnState = {
        "context": context,
        "hits": (),
        "citations": (),
        "rejected": (),
        "steps": (),
        "repaired": False,
    }
    return TURN_GRAPH.invoke(initial)
