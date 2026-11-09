"""Memoria operativa de la conversación sobre los checkpoints de LangGraph."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph


class MemoryState(TypedDict, total=False):
    """Estado serializable que guarda el checkpoint; no contiene dependencias."""

    memory_thread_id: str
    history: list[dict]
    fingerprint: str


@dataclass(frozen=True, slots=True)
class HistoryTurn:
    """Mensaje confirmado del historial visible."""

    seq: int
    role: str
    content: str

    def as_dict(self) -> dict:
        return {"seq": self.seq, "role": self.role, "content": self.content}


@dataclass(frozen=True, slots=True)
class MemorySnapshot:
    """Instantánea del historial guardada en el checkpoint."""

    owner: str
    history: tuple[HistoryTurn, ...]
    fingerprint: str


def fingerprint(turns: Sequence[HistoryTurn]) -> str:
    """Identifica el último mensaje confirmado de una selección de historial."""
    if not turns:
        return "empty"
    return f"{len(turns)}:{turns[-1].seq}"


def _remember(state: MemoryState) -> MemoryState:
    return state


def _build_graph(saver: SqliteSaver):
    builder = StateGraph(MemoryState)
    builder.add_node("remember", _remember)
    builder.add_edge(START, "remember")
    builder.add_edge("remember", END)
    return builder.compile(checkpointer=saver)


class MemoryStore:
    """Checkpointer de LangGraph con `thread_id = conversation_id`."""

    def __init__(self, graph, connection: sqlite3.Connection) -> None:
        self._graph = graph
        self._connection = connection

    def read(self, conversation_id: str) -> tuple[str, MemorySnapshot | None]:
        """Devuelve ``ok``, ``missing`` o ``foreign`` según la instantánea."""
        state = self._graph.get_state({"configurable": {"thread_id": conversation_id}})
        values = state.values or {}
        if not values:
            return "missing", None
        owner = values.get("memory_thread_id")
        if owner != conversation_id:
            return "foreign", None
        history = tuple(HistoryTurn(**item) for item in values.get("history", []))
        return "ok", MemorySnapshot(
            owner=owner,
            history=history,
            fingerprint=values.get("fingerprint", "empty"),
        )

    def write(self, conversation_id: str, turns: Sequence[HistoryTurn]) -> None:
        self.write_snapshot(
            conversation_id,
            MemorySnapshot(
                owner=conversation_id,
                history=tuple(turns),
                fingerprint=fingerprint(turns),
            ),
        )

    def write_snapshot(self, thread_id: str, snapshot: MemorySnapshot) -> None:
        """Escribe una instantánea; el hilo del checkpoint es el de la conversación."""
        self._graph.invoke(
            {
                "memory_thread_id": snapshot.owner,
                "history": [turn.as_dict() for turn in snapshot.history],
                "fingerprint": snapshot.fingerprint,
            },
            {"configurable": {"thread_id": thread_id}},
        )

    def close(self) -> None:
        self._connection.close()


def open_memory(path: Path) -> MemoryStore:
    """Abre `storage/checkpoints.sqlite` con el checkpointer de LangGraph."""
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), check_same_thread=False)
    saver = SqliteSaver(connection)
    saver.setup()
    return MemoryStore(_build_graph(saver), connection)
