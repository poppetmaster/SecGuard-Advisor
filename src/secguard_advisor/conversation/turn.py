"""Ejecución de un turno: creación de la ejecución y cierre clasificado."""

from __future__ import annotations

import contextlib
import time
from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.conversation import service
from secguard_advisor.conversation.budget import (
    ContextBudgetExceeded,
    ContextBudgetUnavailable,
)
from secguard_advisor.conversation.context import TurnContext, TurnDependencies
from secguard_advisor.conversation.graph import run_turn_graph
from secguard_advisor.conversation.llm import (
    InvalidModelOutput,
    ModelTimeout,
    ModelUnavailable,
    RunTimeout,
    StepLimit,
    elapsed_ms,
)
from secguard_advisor.conversation.nodes import generation_config  # noqa: F401
from secguard_advisor.conversation.persistence import StepRecord, fail_run
from secguard_advisor.conversation.prompts import PROMPT_VERSION
from secguard_advisor.db.models import utc_now_iso
from secguard_advisor.evidence.runs import ActiveRunConflict, create_run, record_trace
from secguard_advisor.evidence.tracing import build_tracer
from secguard_advisor.tools.findings import ToolExecutionError, ToolTimeout


@dataclass(frozen=True, slots=True)
class TurnResult:
    """Resultado del turno con su estado HTTP asociado."""

    status: str
    outcome: str | None
    http_status: int
    error_code: str | None


def start_question_turn(
    factory: sessionmaker[Session],
    settings: Settings,
    *,
    scope: CaseScope,
    question: str,
    generator: object,
    embedder: object,
    index: object,
    token_counter,
) -> TurnContext:
    """Crea conversación, pregunta y ejecución en una transacción corta."""
    with factory() as session:
        conversation = service.get_or_create_conversation(session, scope.case_id)
        message = service.create_question_message(session, conversation.id, question)

        try:
            run = create_run(
                session,
                case_id=scope.case_id,
                conversation_id=conversation.id,
                question_message_id=message.id,
                generator_model=getattr(generator, "model", settings.ollama_model),
                generator_digest=getattr(generator, "digest", None),
                generator_num_ctx=settings.generator_num_ctx,
                generator_temperature=settings.generator_temperature,
                generator_seed=settings.generator_seed,
                embedding_model=getattr(embedder, "model", settings.ollama_embedding_model),
                embedding_dim=getattr(embedder, "dimension", settings.embedding_dim),
                prompt_version=PROMPT_VERSION,
            )
        except ActiveRunConflict:
            session.rollback()
            raise

        message.run_id = run.id
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
            conversation_id=conversation.id,
            question_message_id=message.id,
            run_id=run.id,
            attempt_no=run.attempt_no,
            question=question,
            started_perf=time.perf_counter(),
            started_at=utc_now_iso(),
        )


def execute_turn(context: TurnContext, *, memory=None) -> TurnResult:
    """Ejecuta el grafo, clasifica el cierre y registra la traza externa."""
    settings = context.deps.settings
    tracer = build_tracer(settings)
    tracer.start(
        run_id=context.run_id,
        case_id=context.scope.case_id,
        attempt_no=context.attempt_no,
        prompt_version=PROMPT_VERSION,
        question_length=len(context.question),
        metadata={
            "conversation_id": context.conversation_id,
            "generator_model": getattr(context.deps.generator, "model", settings.ollama_model),
            "generator_digest": getattr(context.deps.generator, "digest", None),
            "embedding_model": getattr(
                context.deps.embedder, "model", settings.ollama_embedding_model
            ),
            "embedding_dim": getattr(context.deps.embedder, "dimension", settings.embedding_dim),
        },
    )
    result = _execute_turn(context, memory, tracer)
    trace = tracer.finish(
        status=result.status,
        outcome=result.outcome,
        duration_ms=int((time.perf_counter() - context.started_perf) * 1000),
    )
    with contextlib.suppress(Exception):
        record_trace(
            context.factory,
            context.run_id,
            status=trace.status,
            trace_id=trace.trace_id,
            trace_url=trace.trace_url,
        )
    return result


def _execute_turn(context: TurnContext, memory, tracer) -> TurnResult:
    try:
        state = run_turn_graph(context, memory, tracer)
    except StepLimit:
        _fail(
            context,
            status="failed",
            code="step_limit",
            message="Se excedió el máximo de operaciones del turno.",
            step_name="limits",
        )
        return TurnResult("failed", "error", 500, "step_limit")
    except ToolTimeout:
        _fail(
            context,
            status="timeout",
            code="tool_timeout",
            message="La consulta de hallazgos excedió el tiempo de espera.",
            step_name="tools",
        )
        return TurnResult("timeout", "error", 504, "tool_timeout")
    except ToolExecutionError:
        _fail(
            context,
            status="failed",
            code="tool_failed",
            message="No se pudieron consultar los hallazgos del caso.",
            step_name="tools",
        )
        return TurnResult("failed", "error", 500, "tool_failed")
    except ContextBudgetUnavailable as exc:
        _fail(
            context,
            status="failed",
            code="context_budget_unavailable",
            message=str(exc),
        )
        return TurnResult("failed", "error", 503, "context_budget_unavailable")
    except ContextBudgetExceeded as exc:
        _fail(
            context,
            status="failed",
            code="context_budget_exceeded",
            message=str(exc),
        )
        return TurnResult("failed", "error", 500, "context_budget_exceeded")
    except RunTimeout:
        _fail(
            context, status="timeout", code="run_timeout", message="Se agotó el tiempo del turno."
        )
        return TurnResult("timeout", "error", 504, "run_timeout")
    except ModelTimeout:
        _fail(
            context,
            status="timeout",
            code="model_timeout",
            message="Se agotó el tiempo de espera del modelo.",
        )
        return TurnResult("timeout", "error", 504, "model_timeout")
    except ModelUnavailable:
        _fail(
            context,
            status="failed",
            code="model_unavailable",
            message="El modelo local no responde.",
        )
        return TurnResult("failed", "error", 503, "model_unavailable")
    except InvalidModelOutput:
        _fail(
            context,
            status="failed",
            code="invalid_model_output",
            message="La salida del modelo no cumple el esquema esperado.",
        )
        return TurnResult("failed", "error", 500, "invalid_model_output")
    except Exception:
        _fail(
            context,
            status="failed",
            code="internal_error",
            message="Ocurrió un error interno durante la consulta.",
        )
        return TurnResult("failed", "error", 500, "internal_error")

    outcome = state.get("outcome") or "error"
    return TurnResult("succeeded", outcome, 200, None)


def _fail(
    context: TurnContext, *, status: str, code: str, message: str, step_name: str = "agent"
) -> None:
    duration = elapsed_ms(context.started_perf)
    fail_run(
        context.factory,
        run_id=context.run_id,
        status=status,
        error_code=code,
        error_message=message,
        duration_ms=duration,
        steps=(
            StepRecord(
                name=step_name,
                origin="model",
                status="error",
                duration_ms=duration,
                detail={"error": code},
            ),
        ),
    )
