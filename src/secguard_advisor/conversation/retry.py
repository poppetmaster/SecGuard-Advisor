"""Reintento de un turno fallido sobre la pregunta existente."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.cases.service import get_case
from secguard_advisor.config import Settings
from secguard_advisor.conversation.context import TurnContext
from secguard_advisor.conversation.turn import build_turn_context, create_turn_record
from secguard_advisor.db.models import Message, Run
from secguard_advisor.evidence.runs import ActiveRunConflict

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
        case = get_case(session, scope)
        try:
            run, authorization = create_turn_record(
                session,
                settings,
                scope,
                conversation_id=original.conversation_id,
                question_message_id=plan.question_message_id,
                generator=generator,
                embedder=embedder,
                attempt_no=plan.attempt_no,
                retry_of_run_id=original.id,
            )
        except ActiveRunConflict:
            session.rollback()
            raise
        session.commit()
        return build_turn_context(
            factory=factory,
            settings=settings,
            scope=scope,
            generator=generator,
            embedder=embedder,
            index=index,
            token_counter=token_counter,
            conversation_id=original.conversation_id,
            question_message_id=plan.question_message_id,
            run=run,
            authorization=authorization,
            question=plan.question,
            case=case,
        )
