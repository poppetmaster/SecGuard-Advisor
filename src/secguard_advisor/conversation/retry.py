"""Reintento de un turno fallido sobre la pregunta existente."""

from __future__ import annotations

import time
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.conversation.context import TurnContext, TurnDependencies
from secguard_advisor.conversation.prompts import PROMPT_VERSION
from secguard_advisor.db.models import Message, Run, utc_now_iso
from secguard_advisor.evidence.runs import ActiveRunConflict, create_run

RETRYABLE_STATUSES = {"failed", "timeout", "interrupted"}


class RunNotFound(LookupError):
    """La ejecución no existe en el caso autorizado."""


class RetryNotAllowed(RuntimeError):
    """La ejecución no admite reintento."""


@dataclass(frozen=True, slots=True)
class RetryPlan:
    run_id: str
    question_message_id: str
    question: str
    attempt_no: int


def plan_retry(factory: sessionmaker[Session], scope: CaseScope, run_id: str) -> RetryPlan:
    """Valida que el turno sea reintentable y calcula el número de intento."""
    with factory() as session:
        run = session.get(Run, run_id)
        if run is None or run.case_id != scope.case_id:
            raise RunNotFound(run_id)
        if run.answer_message_id is not None:
            raise RetryNotAllowed("El turno ya tiene una respuesta persistida.")
        if run.status not in RETRYABLE_STATUSES:
            raise RetryNotAllowed("Solo se reintenta un turno fallido, interrumpido o agotado.")
        if not run.question_message_id:
            raise RetryNotAllowed("La ejecución no tiene pregunta asociada.")
        question = session.get(Message, run.question_message_id)
        if question is None:
            raise RetryNotAllowed("La pregunta original ya no existe.")
        highest = session.scalar(
            select(func.max(Run.attempt_no)).where(
                Run.question_message_id == run.question_message_id
            )
        )
        return RetryPlan(
            run_id=run.id,
            question_message_id=run.question_message_id,
            question=question.content,
            attempt_no=(highest or 0) + 1,
        )


def start_retry_turn(
    factory: sessionmaker[Session],
    settings: Settings,
    *,
    scope: CaseScope,
    run_id: str,
    generator: object,
    embedder: object,
    index: object,
    token_counter,
) -> TurnContext:
    """Crea una ejecución nueva que reutiliza la pregunta original."""
    plan = plan_retry(factory, scope, run_id)
    with factory() as session:
        original = session.get(Run, plan.run_id)
        if original is None or original.case_id != scope.case_id:
            raise RunNotFound(plan.run_id)
        try:
            run = create_run(
                session,
                case_id=original.case_id,
                conversation_id=original.conversation_id,
                question_message_id=plan.question_message_id,
                generator_model=getattr(generator, "model", settings.ollama_model),
                generator_digest=getattr(generator, "digest", None),
                generator_num_ctx=settings.generator_num_ctx,
                generator_temperature=settings.generator_temperature,
                generator_seed=settings.generator_seed,
                embedding_model=getattr(embedder, "model", settings.ollama_embedding_model),
                embedding_dim=getattr(embedder, "dimension", settings.embedding_dim),
                prompt_version=PROMPT_VERSION,
                attempt_no=plan.attempt_no,
                retry_of_run_id=original.id,
            )
        except ActiveRunConflict:
            session.rollback()
            raise
        session.commit()
        return TurnContext(
            factory=factory,
            deps=TurnDependencies(
                generator=generator,
                embedder=embedder,
                index=index,
                settings=settings,
                token_counter=token_counter,
            ),
            scope=scope,
            conversation_id=original.conversation_id,
            question_message_id=plan.question_message_id,
            run_id=run.id,
            attempt_no=run.attempt_no,
            question=plan.question,
            started_perf=time.perf_counter(),
            started_at=utc_now_iso(),
        )
