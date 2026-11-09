"""Grafo del turno documental: memoria, recuperar, generar, validar y persistir."""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from secguard_advisor.conversation.nodes import (
    abstain,
    agent,
    decide,
    load_memory,
    load_scope,
    persist,
    repair,
    retrieve,
    route_after_decide,
    route_after_validate,
    tools,
    validate,
)


class TurnState(TypedDict, total=False):
    """Estado del turno; las dependencias viajan por configuración, no por estado."""

    question: str
    history: tuple
    memory_status: str
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
    tool_results: tuple
    tool_records: tuple
    tool_calls: int
    tool_budget: int
    decision: dict


def build_turn_graph():
    """Compone el grafo con memoria, una única reparación de citas y persistencia."""
    builder = StateGraph(TurnState)
    builder.add_node("load_scope", load_scope)
    builder.add_node("load_memory", load_memory)
    builder.add_node("retrieve", retrieve)
    builder.add_node("agent", agent)
    builder.add_node("decide", decide)
    builder.add_node("tools", tools)
    builder.add_node("validate", validate)
    builder.add_node("repair", repair)
    builder.add_node("abstain", abstain)
    builder.add_node("persist", persist)

    builder.add_edge(START, "load_scope")
    builder.add_edge("load_scope", "load_memory")
    builder.add_edge("load_memory", "retrieve")
    builder.add_edge("retrieve", "decide")
    builder.add_conditional_edges(
        "decide",
        route_after_decide,
        {"tools": "tools", "agent": "agent"},
    )
    builder.add_edge("tools", "decide")
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


def run_turn_graph(context, memory=None) -> dict[str, Any]:
    """Ejecuta el turno con las dependencias y el checkpointer en configuración."""
    initial: TurnState = {
        "question": context.question,
        "history": (),
        "hits": (),
        "citations": (),
        "rejected": (),
        "steps": (),
        "repaired": False,
        "tool_results": (),
        "tool_records": (),
        "tool_calls": 0,
        "tool_budget": 2,
        "decision": {"use_findings": False, "arguments": {}},
    }
    config = {"configurable": {"runtime": context, "memory": memory}}
    return TURN_GRAPH.invoke(initial, config)
