"""Ciclo de vida mínimo de las ejecuciones."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from secguard_advisor.db.models import Run, utc_now_iso

_RUN_STATUSES = {"succeeded", "failed", "timeout", "interrupted"}


class ActiveRunConflict(RuntimeError):
    """El caso ya tiene una ejecución activa."""


class DuplicateAttempt(RuntimeError):
    """El número de intento ya existe para la pregunta."""


def _classify_integrity_error(exc: IntegrityError) -> RuntimeError:
    message = str(exc.orig)
    if "ux_runs_one_active_per_case" in message or "runs.case_id" in message:
        return ActiveRunConflict("El caso ya tiene una consulta en curso.")
    if "uq_runs_question_attempt" in message or "runs.question_message_id" in message:
        return DuplicateAttempt("El intento ya existe para esta pregunta.")
    return RuntimeError(str(exc))


def create_run(
    session: Session,
    *,
    case_id: str,
    conversation_id: str,
    question_message_id: str,
    generator_model: str,
    generator_num_ctx: int,
    generator_temperature: float,
    embedding_model: str,
    embedding_dim: int,
    prompt_version: str,
    attempt_no: int = 1,
    retry_of_run_id: str | None = None,
    generator_digest: str | None = None,
    generator_seed: int | None = None,
) -> Run:
    """Crea la ejecución sin confirmar la transacción del llamador."""
    run = Run(
        case_id=case_id,
        conversation_id=conversation_id,
        question_message_id=question_message_id,
        attempt_no=attempt_no,
        retry_of_run_id=retry_of_run_id,
        generator_model=generator_model,
        generator_digest=generator_digest,
        generator_num_ctx=generator_num_ctx,
        generator_temperature=generator_temperature,
        generator_seed=generator_seed,
        embedding_model=embedding_model,
        embedding_dim=embedding_dim,
        prompt_version=prompt_version,
    )
    session.add(run)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise _classify_integrity_error(exc) from exc
    return run


def close_run(
    session: Session,
    run: Run,
    *,
    status: str,
    outcome: str | None = None,
    duration_ms: int | None = None,
    answer_message_id: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> Run:
    """Cierra la ejecución sin confirmar la transacción del llamador."""
    if status not in _RUN_STATUSES:
        raise ValueError(f"Estado de ejecución inválido: {status}")

    run.status = status
    run.outcome = outcome
    run.duration_ms = duration_ms
    run.answer_message_id = answer_message_id
    run.error_code = error_code
    run.error_message = error_message
    run.finished_at = utc_now_iso()
    session.add(run)
    return run
