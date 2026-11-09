"""Contexto de un turno de conversación."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings


@dataclass(frozen=True, slots=True)
class TurnDependencies:
    """Dependencias externas del turno, inyectables en pruebas."""

    generator: object
    embedder: object
    index: object
    settings: Settings
    token_counter: object


@dataclass(frozen=True, slots=True)
class TurnContext:
    """Identidades y dependencias ya resueltas para ejecutar un turno."""

    factory: sessionmaker[Session]
    deps: TurnDependencies
    scope: CaseScope
    conversation_id: str
    question_message_id: str
    run_id: str
    question: str
    started_perf: float
    started_at: str
