"""Ciclo de vida y lectura de la evidencia de ejecución."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from secguard_advisor.db.models import (
    Document,
    DocumentChunk,
    DocumentVersion,
    Run,
    RunSource,
    RunStep,
    RunToolCall,
    utc_now_iso,
)
from secguard_advisor.tools.findings import FindingsQuery

_RUN_STATUSES = {"succeeded", "failed", "timeout", "interrupted"}
_TRACE_STATUSES = {"disabled", "submitted", "failed"}

ORIGIN_LABELS = {
    "public_corpus": "Corpus público",
    "case_evidence": "Evidencia del caso",
}

TOOL_STATUS_LABELS = {
    "ok": "Consulta completada",
    "invalid_arguments": "Argumentos inválidos",
    "error": "Error de la herramienta",
}

RETRYABLE_STATUSES = {"failed", "timeout", "interrupted"}


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


def record_trace(
    factory: sessionmaker[Session],
    run_id: str,
    *,
    status: str,
    trace_id: str | None = None,
    trace_url: str | None = None,
) -> None:
    """Persiste el resultado del envío de traza en una transacción corta.

    ``confirmed`` nunca se escribe desde la aplicación: corresponde al script de
    confirmación de la aceptación (T091).
    """
    if status not in _TRACE_STATUSES:
        raise ValueError(f"Estado de traza no permitido por la aplicación: {status}")
    with factory() as session:
        run = session.get(Run, run_id)
        if run is None:
            return
        run.trace_status = status
        run.trace_id = trace_id
        run.trace_url = trace_url
        session.commit()


def serialize_steps(session: Session, run_id: str) -> list[dict]:
    """Pasos registrados, con su detalle histórico ya serializado."""
    rows = list(
        session.scalars(select(RunStep).where(RunStep.run_id == run_id).order_by(RunStep.seq))
    )
    return [
        {
            "seq": step.seq,
            "name": step.name,
            "origin": step.origin,
            "status": step.status,
            "duration_ms": step.duration_ms,
            "detail": json.loads(step.detail_json) if step.detail_json else None,
        }
        for step in rows
    ]


def serialize_sources(session: Session, run_id: str) -> list[dict]:
    """Fuentes recuperadas y si fueron citadas en la respuesta."""
    rows = list(
        session.scalars(
            select(RunSource).where(RunSource.run_id == run_id).order_by(RunSource.rank)
        )
    )
    sources: list[dict] = []
    for row in rows:
        chunk = session.get(DocumentChunk, row.chunk_id)
        version = session.get(DocumentVersion, chunk.version_id) if chunk is not None else None
        document = session.get(Document, version.document_id) if version is not None else None
        sources.append(
            {
                "rank": row.rank,
                "origin": row.origin,
                "origin_label": ORIGIN_LABELS.get(row.origin, row.origin),
                "title": document.title if document else "Documento",
                "page": chunk.page_start if chunk else None,
                "section": chunk.section if chunk else None,
                "score": round(row.score, 4),
                "used_in_answer": row.used_in_answer,
            }
        )
    return sources


def _summary_snapshot(summary: dict | None) -> dict | None:
    """Instantánea conservada en el resumen, con o sin bloques por origen."""
    if not summary:
        return None
    snapshot = summary.get("snapshot")
    if isinstance(snapshot, dict) and snapshot.get("id"):
        return snapshot
    for block in summary.get("origins") or ():
        if not isinstance(block, dict):
            continue
        snapshot = block.get("snapshot")
        if isinstance(snapshot, dict) and snapshot.get("id"):
            return snapshot
    return None


def _detail_arguments(arguments: dict, snapshot: dict | None) -> dict:
    """Reutiliza los filtros originales y fija la instantánea registrada.

    Sin `snapshot_id`, la consulta actual volvería a resolver «la última» y
    falsearía el detalle histórico. La instantánea del resumen manda.
    """
    detail_arguments = dict(arguments)
    if snapshot is None:
        return detail_arguments
    detail_arguments["snapshot_id"] = snapshot["id"]
    if detail_arguments.get("origin") in {None, "all"}:
        detail_arguments["origin"] = "imported"
    return detail_arguments


def serialize_tool_calls(
    session: Session,
    run_id: str,
    *,
    factory=None,
    scope=None,
) -> list[dict]:
    """Invocaciones registradas; separa el resumen histórico del detalle actual.

    El resumen (totales, grupos, procedencia) es el resultado original persistido.
    Las filas de detalle no se persisten: si el contrato las pidió, se recalculan
    en modo lectura y se marcan explícitamente como una consulta actual.
    """
    rows = list(
        session.scalars(
            select(RunToolCall).where(RunToolCall.run_id == run_id).order_by(RunToolCall.seq)
        )
    )
    views: list[dict] = []
    for row in rows:
        arguments = json.loads(row.arguments_json) if row.arguments_json else {}
        summary = json.loads(row.result_summary_json) if row.result_summary_json else None
        detail_items = None
        detail_error = None
        detail_source = None
        detail_snapshot = _summary_snapshot(summary)
        if summary and arguments.get("detail") and factory is not None and scope is not None:
            detail_source = "current_query"
            detail_arguments = _detail_arguments(arguments, detail_snapshot)
            try:
                detail_items = (
                    FindingsQuery(factory, scope).execute(detail_arguments).get("items", [])
                )
            except Exception:
                detail_error = "No se pudo recalcular el detalle de la consulta."
        views.append(
            {
                "tool_name": row.tool_name,
                "status": row.status,
                "status_label": TOOL_STATUS_LABELS.get(row.status, row.status),
                "error_code": row.error_code,
                "duration_ms": row.duration_ms,
                "arguments": arguments,
                "summary": summary,
                "detail_items": detail_items,
                "detail_source": detail_source,
                "detail_snapshot": detail_snapshot,
                "detail_error": detail_error,
                "is_synthetic": bool(
                    summary and isinstance(summary.get("dataset"), dict) and summary["dataset"]
                ),
            }
        )
    return views


def serialize_attempts(session: Session, run: Run) -> list[dict]:
    """Intentos de la misma pregunta, en orden, con el actual marcado."""
    if not run.question_message_id:
        return []
    rows = list(
        session.scalars(
            select(Run)
            .where(Run.question_message_id == run.question_message_id)
            .order_by(Run.attempt_no)
        )
    )
    return [
        {
            "id": item.id,
            "attempt_no": item.attempt_no,
            "retry_of_run_id": item.retry_of_run_id,
            "status": item.status,
            "outcome": item.outcome,
            "started_at": item.started_at,
            "is_current": item.id == run.id,
        }
        for item in rows
    ]


def retry_allowed(run: Run) -> bool:
    """Un intento se reintenta solo si falló y no dejó respuesta."""
    return run.answer_message_id is None and run.status in RETRYABLE_STATUSES
