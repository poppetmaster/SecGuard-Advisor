"""Nodos deterministas y de modelo del grafo conversacional."""

from __future__ import annotations

import time
from typing import Any

from secguard_advisor.cases.scope import require_case
from secguard_advisor.conversation import service
from secguard_advisor.conversation.budget import check_prompt, plan_prompt
from secguard_advisor.conversation.llm import (
    AnswerPayload,
    Claim,
    GenerationConfig,
    ModelTimeout,
    RunTimeout,
    StepLimit,
    elapsed_ms,
)
from secguard_advisor.conversation.persistence import (
    CitationDraft,
    StepRecord,
    ToolCallRecord,
    fail_run,
    persist_turn,
)
from secguard_advisor.conversation.prompts import (
    DECISION_SYSTEM_PROMPT,
    build_decision_prompt,
)
from secguard_advisor.evidence.tracing import NullTracer
from secguard_advisor.retrieval.citations import check_citation
from secguard_advisor.retrieval.search import RetrievedChunk, search_documents
from secguard_advisor.tools.findings import (
    TOOL_NAME,
    FindingsQuery,
    ToolArgumentError,
)

INSUFFICIENT_EVIDENCE_TEXT = (
    "No encontré evidencia documental suficiente en las fuentes disponibles del caso y del "
    "corpus público para responder esta pregunta. No voy a inventar una respuesta fundamentada. "
    "Cargá documentos pertinentes o reformulá la consulta dentro del alcance cubierto."
)

ABSTAINED_CITATIONS_TEXT = (
    "La respuesta propuesta no pudo sostenerse con citas verificables, así que no la presento "
    "como fundamentada. Revisá los documentos disponibles o reformulá la pregunta para que la "
    "evidencia recuperada alcance."
)


def _append(state: dict, step: StepRecord) -> tuple[StepRecord, ...]:
    return (*state.get("steps", ()), step)


def record_step(
    state: dict, name: str, origin: str, status: str, started: float, detail: dict | None = None
) -> tuple[StepRecord, ...]:
    return _append(
        state,
        StepRecord(
            name=name,
            origin=origin,
            status=status,
            duration_ms=elapsed_ms(started),
            detail=detail,
        ),
    )


def runtime_of(config) -> Any:
    """Dependencias del turno: viajan por configuración, nunca por el checkpoint."""
    return config["configurable"]["runtime"]


def memory_of(config):
    return config["configurable"].get("memory") if config else None


def tracer_of(config):
    """Traza del turno; ausente en pruebas rápidas, nunca inventa un envío."""
    if not config:
        return NullTracer()
    return config["configurable"].get("tracer") or NullTracer()


def _remaining_turn_seconds(context) -> float:
    return max(
        0.0,
        context.deps.settings.run_timeout_seconds - (time.perf_counter() - context.started_perf),
    )


def _model_timeout(context) -> float:
    """Tiempo máximo de esta llamada: nunca supera el tiempo restante del turno."""
    remaining = _remaining_turn_seconds(context)
    if remaining <= 0:
        raise RunTimeout("Se agotó el tiempo del turno.")
    return min(context.deps.settings.llm_timeout_seconds, remaining)


def _call_model(context, call, timeout_seconds: float):
    """Ejecuta una llamada al modelo y distingue timeout de llamada y de turno."""
    try:
        return call(timeout_seconds=timeout_seconds)
    except ModelTimeout:
        if timeout_seconds < context.deps.settings.llm_timeout_seconds:
            raise RunTimeout("Se agotó el tiempo del turno.") from None
        raise


def _consume_step(state: dict, context) -> int:
    """Cuenta una operación de modelo o herramienta; la preparación no cuenta."""
    count = state.get("step_count", 0) + 1
    if count > context.deps.settings.max_graph_steps:
        raise StepLimit("Se excedió el máximo de operaciones del turno.")
    return count


def resolve_source_id(source_id: str, hits: tuple[RetrievedChunk, ...]) -> str | None:
    """Acepta el identificador real del fragmento o la etiqueta S1, S2, ..."""
    cleaned = (source_id or "").strip()
    if not cleaned:
        return None
    for hit in hits:
        if cleaned == hit.chunk_id:
            return hit.chunk_id
    if cleaned.upper().startswith("S") and cleaned[1:].isdigit():
        index = int(cleaned[1:]) - 1
        if 0 <= index < len(hits):
            return hits[index].chunk_id
    return None


def load_scope(state: dict[str, Any], config) -> dict[str, Any]:
    started = time.perf_counter()
    context = runtime_of(config)
    with context.factory() as session:
        require_case(session, context.scope)
    tracer_of(config).operation(
        "load_scope",
        run_type="chain",
        inputs={},
        outputs={"status": "ok"},
        duration_ms=elapsed_ms(started),
    )
    return {"steps": record_step(state, "load_scope", "deterministic", "ok", started)}


def load_memory(state: dict[str, Any], config) -> dict[str, Any]:
    """Carga el historial confirmado y alinea el checkpoint con la base de negocio."""
    started = time.perf_counter()
    context = runtime_of(config)
    settings = context.deps.settings
    with context.factory() as session:
        turns = service.load_confirmed_history(
            session,
            context.conversation_id,
            exclude_message_id=context.question_message_id,
            max_messages=settings.history_max_messages,
            max_chars=settings.history_max_chars,
        )

    memory = memory_of(config)
    status = "disabled"
    if memory is not None:
        try:
            status = service.reconcile_memory(memory, context.conversation_id, turns)
        except Exception:
            status = "failed"

    tracer_of(config).operation(
        "load_memory",
        run_type="chain",
        inputs={
            "history_max_messages": settings.history_max_messages,
            "history_max_chars": settings.history_max_chars,
        },
        outputs={"messages": len(turns), "memory": status},
        duration_ms=elapsed_ms(started),
    )
    return {
        "history": turns,
        "memory_status": status,
        "steps": record_step(
            state,
            "load_memory",
            "deterministic",
            "ok",
            started,
            {"messages": len(turns), "memory": status},
        ),
    }


def retrieve(state: dict[str, Any], config) -> dict[str, Any]:
    started = time.perf_counter()
    context = runtime_of(config)
    settings = context.deps.settings
    query = service.retrieval_query(context.question, state.get("history", ()))
    with context.factory() as session:
        result = search_documents(
            session,
            scope=context.scope,
            query=query,
            embedder=context.deps.embedder,
            index=context.deps.index,
            top_k=settings.retrieval_top_k,
            min_score=settings.retrieval_min_score,
            token_budget=settings.retrieval_token_budget,
        )
    origin_counts: dict[str, int] = {}
    for hit in result.hits:
        origin_counts[hit.origin] = origin_counts.get(hit.origin, 0) + 1
    tracer_of(config).operation(
        "retrieve",
        run_type="retriever",
        inputs={
            "query_length": len(context.question),
            "top_k": settings.retrieval_top_k,
            "min_score": settings.retrieval_min_score,
            "token_budget": settings.retrieval_token_budget,
        },
        outputs={
            "hits": len(result.hits),
            "status": result.status,
            "origin_counts": origin_counts,
        },
        duration_ms=elapsed_ms(started),
    )
    return {
        "hits": result.hits,
        "retrieval_status": result.status,
        "steps": record_step(
            state,
            "retrieve",
            "deterministic",
            "ok",
            started,
            {"hits": len(result.hits), "status": result.status},
        ),
    }


def _check_turn_deadline(context) -> None:
    if time.perf_counter() - context.started_perf > context.deps.settings.run_timeout_seconds:
        raise RunTimeout("Se agotó el tiempo del turno.")


def agent(state: dict[str, Any], config) -> dict[str, Any]:
    started = time.perf_counter()
    context = runtime_of(config)
    step_count = _consume_step(state, context)
    plan = plan_prompt(
        question=context.question,
        hits=state.get("hits", ()),
        history=state.get("history", ()),
        settings=context.deps.settings,
        counter=context.deps.token_counter,
        tool_results=state.get("tool_results", ()),
    )
    timeout = _model_timeout(context)
    tracer = tracer_of(config)
    try:
        payload = _call_model(
            context,
            lambda **kwargs: context.deps.generator.generate(
                system=plan.system, user=plan.user, **kwargs
            ),
            timeout,
        )
    except Exception as exc:
        tracer.operation(
            "agent.generate",
            run_type="llm",
            inputs={"model": context.deps.generator.model},
            error=type(exc).__name__,
        )
        raise
    usage = getattr(context.deps.generator, "last_usage", None) or {}
    plan_detail = plan.detail()
    tracer.operation(
        "agent.generate",
        run_type="llm",
        inputs={
            "model": context.deps.generator.model,
            "prompt_version": plan_detail.get("prompt_version"),
            "admitted_tokens": plan_detail.get("admitted_tokens"),
            "history_messages": plan_detail.get("history_messages"),
            "sources": plan_detail.get("sources"),
            "dropped_history_messages": plan_detail.get("dropped_history_messages"),
            "dropped_sources": plan_detail.get("dropped_sources"),
            "limit": plan_detail.get("limit"),
        },
        outputs={
            "claims": len(payload.claims),
            "answer_length": len(payload.answer),
            "missing_info": len(payload.missing_info),
            "recommendations": len(payload.recommendations),
        },
        duration_ms=elapsed_ms(started),
    )
    _check_turn_deadline(context)
    return {
        "payload": payload,
        "hits": plan.hits,
        "tool_budget": context.deps.settings.max_tool_calls,
        "step_count": step_count,
        "steps": record_step(
            state,
            "agent",
            "model",
            "ok",
            started,
            {
                "claims": len(payload.claims),
                **plan.detail(),
                "observed_prompt_tokens": usage.get("prompt_tokens"),
            },
        ),
    }


def _tool_summary(result: dict) -> dict:
    summary = {
        "origin": result.get("origin"),
        "total": result.get("total", 0),
        "truncated": result.get("truncated", False),
        "items_count": len(result.get("items", [])),
    }
    for key in (
        "groups",
        "origins",
        "dataset",
        "snapshot",
        "status_group",
        "status_counts",
        "severity_counts",
        "exploitability_counts",
        "malware_counts",
        "manual_review_rows",
        "severity_scale",
        "priority_counts",
        "empty_reason",
    ):
        if key in result:
            summary[key] = result[key]
    return summary


def _selected_snapshot_from_result(result: dict) -> str | None:
    snapshot = result.get("snapshot")
    if isinstance(snapshot, dict) and snapshot.get("id"):
        return str(snapshot["id"])
    for block in result.get("origins", ()):  # origin=all
        if isinstance(block, dict):
            snapshot = block.get("snapshot")
            if isinstance(snapshot, dict) and snapshot.get("id"):
                return str(snapshot["id"])
    return None


def decide(state: dict[str, Any], config) -> dict[str, Any]:
    """El modelo decide, con un esquema propio, si necesita findings_query."""
    started = time.perf_counter()
    context = runtime_of(config)
    settings = context.deps.settings
    if state.get("tool_calls", 0) >= settings.max_tool_calls:
        return {
            "decision": {"use_findings": False, "arguments": {}},
            "steps": record_step(
                state,
                "decide",
                "model",
                "ok",
                started,
                {"use_findings": False, "reason": "tool_call_limit"},
            ),
        }

    step_count = _consume_step(state, context)
    user_prompt = build_decision_prompt(
        context.question,
        state.get("history", ()),
        tuple(state.get("tool_results", ())),
    )
    admitted = check_prompt(
        system=DECISION_SYSTEM_PROMPT,
        user=user_prompt,
        settings=settings,
        counter=context.deps.token_counter,
    )
    timeout = _model_timeout(context)
    tracer = tracer_of(config)
    try:
        decision = _call_model(
            context,
            lambda **kwargs: context.deps.generator.decide(
                system=DECISION_SYSTEM_PROMPT, user=user_prompt, **kwargs
            ),
            timeout,
        )
    except Exception as exc:
        tracer.operation(
            "tool.decide",
            run_type="llm",
            inputs={"model": context.deps.generator.model},
            error=type(exc).__name__,
        )
        raise
    usage = getattr(context.deps.generator, "last_usage", None) or {}
    tracer.operation(
        "tool.decide",
        run_type="llm",
        inputs={
            "model": context.deps.generator.model,
            "admitted_tokens": admitted,
            "history_messages": len(state.get("history", ())),
            "previous_tool_results": len(state.get("tool_results", ())),
        },
        outputs={
            "use_findings": decision.use_findings,
            "argument_keys": sorted(decision.arguments),
            "argument_count": len(decision.arguments),
        },
        duration_ms=elapsed_ms(started),
    )
    _check_turn_deadline(context)
    return {
        "decision": decision.model_dump(),
        "step_count": step_count,
        "steps": record_step(
            state,
            "decide",
            "model",
            "ok",
            started,
            {
                "use_findings": decision.use_findings,
                "admitted_tokens": admitted,
                "observed_prompt_tokens": usage.get("prompt_tokens"),
            },
        ),
    }


def route_after_decide(state: dict[str, Any]) -> str:
    decision = state.get("decision") or {}
    if decision.get("use_findings"):
        return "tools"
    return "agent"


def tools(state: dict[str, Any], config) -> dict[str, Any]:
    """Ejecuta la llamada solicitada por la decisión del modelo."""
    started = time.perf_counter()
    context = runtime_of(config)
    settings = context.deps.settings
    step_count = _consume_step(state, context)
    remaining = _remaining_turn_seconds(context)
    if remaining <= 0:
        raise RunTimeout("Se agotó el tiempo del turno.")
    decision = state.get("decision") or {}
    arguments = decision.get("arguments") or {}
    selected_import_id = state.get("selected_import_id")
    query = FindingsQuery(
        context.factory,
        context.scope,
        timeout_seconds=min(settings.tool_timeout_seconds, remaining),
    )
    tracer = tracer_of(config)
    results = list(state.get("tool_results", ()))
    records = list(state.get("tool_records", ()))
    call_started = time.perf_counter()
    status = "ok"
    summary = None

    try:
        if selected_import_id is None:
            result = query.execute(arguments)
        else:
            result = query.execute(arguments, fixed_snapshot_id=selected_import_id)
    except ToolArgumentError as exc:
        duration = elapsed_ms(call_started)
        records.append(
            ToolCallRecord(
                tool_name=TOOL_NAME,
                origin="model_requested",
                arguments=arguments,
                summary=None,
                status="invalid_arguments",
                error_code=exc.code,
                duration_ms=duration,
            )
        )
        results.append(
            {
                "tool": TOOL_NAME,
                "status": "invalid_arguments",
                "arguments": arguments,
                "error": {"code": exc.code, "message": exc.message},
            }
        )
        status = "invalid_arguments"
        tracer.operation(
            "findings_query",
            run_type="tool",
            inputs={
                "tool": TOOL_NAME,
                "argument_keys": sorted(arguments),
                "argument_count": len(arguments),
            },
            outputs={"status": status, "error_code": exc.code},
            duration_ms=duration,
        )
    except Exception as exc:
        tracer.operation(
            "findings_query",
            run_type="tool",
            inputs={"tool": TOOL_NAME, "argument_keys": sorted(arguments)},
            error=type(exc).__name__,
        )
        raise
    else:
        duration = elapsed_ms(call_started)
        selected_import_id = selected_import_id or _selected_snapshot_from_result(result)
        summary = _tool_summary(result)
        records.append(
            ToolCallRecord(
                tool_name=TOOL_NAME,
                origin="model_requested",
                arguments=arguments,
                summary=summary,
                status="ok",
                error_code=None,
                duration_ms=duration,
            )
        )
        results.append(
            {
                "tool": TOOL_NAME,
                "status": "ok",
                "arguments": arguments,
                "result": result,
            }
        )
        tracer.operation(
            "findings_query",
            run_type="tool",
            inputs={
                "tool": TOOL_NAME,
                "argument_keys": sorted(arguments),
                "argument_count": len(arguments),
            },
            outputs={
                "status": status,
                "total": summary.get("total"),
                "groups_count": len(summary.get("groups", ())),
                "truncated": summary.get("truncated"),
                "origin": summary.get("origin"),
                "status_group": summary.get("status_group"),
                "snapshot_sequence": (summary.get("snapshot") or {}).get("sequence"),
                "status_counts": summary.get("status_counts"),
                "severity_counts": summary.get("severity_counts"),
                "exploitability_counts": summary.get("exploitability_counts"),
                "malware_counts": summary.get("malware_counts"),
                "manual_review_rows": summary.get("manual_review_rows"),
                "priority_counts": summary.get("priority_counts"),
            },
            duration_ms=duration,
        )

    return {
        "tool_results": tuple(results),
        "tool_records": tuple(records),
        "tool_calls": state.get("tool_calls", 0) + 1,
        "selected_import_id": selected_import_id,
        "step_count": step_count,
        "decision": {"use_findings": False, "arguments": {}},
        "steps": record_step(
            state,
            "tools",
            "deterministic",
            "ok",
            started,
            {"status": status},
        ),
    }


def _draft_for_claim(
    session, context, claim: Claim, hits: tuple[RetrievedChunk, ...]
) -> CitationDraft | None:
    """Devuelve la cita válida de la afirmación o ``None`` si no la hay."""
    if not claim.chunk_ids:
        return None
    for source_id in claim.chunk_ids:
        chunk_id = resolve_source_id(source_id, hits)
        if chunk_id is None:
            continue
        hit = next((item for item in hits if item.chunk_id == chunk_id), None)
        if hit is None:
            continue
        result = check_citation(
            session,
            context.scope,
            chunk_id=chunk_id,
            version_id=hit.version_id,
            page=hit.page,
            section=hit.section,
            quote=claim.quote,
        )
        if result.valid:
            return CitationDraft(
                chunk_id=chunk_id,
                document_id=hit.document_id,
                version_id=hit.version_id,
                page=hit.page,
                section=hit.section,
                quote=claim.quote.strip(),
                locator=hit.locator,
                check_status="valid",
                check_reason=None,
            )
    return None


def _rejected_draft(
    session, context, claim: Claim, hits: tuple[RetrievedChunk, ...]
) -> CitationDraft:
    """Registra el motivo del rechazo de la primera fuente intentada."""
    if not claim.chunk_ids:
        return CitationDraft(
            chunk_id="",
            document_id="",
            version_id="",
            page=None,
            section=None,
            quote=(claim.quote or "").strip()[:400],
            locator="",
            check_status="rejected",
            check_reason="chunk_missing",
        )

    for source_id in claim.chunk_ids:
        chunk_id = resolve_source_id(source_id, hits)
        if chunk_id is None:
            continue
        hit = next((item for item in hits if item.chunk_id == chunk_id), None)
        if hit is None:
            continue
        result = check_citation(
            session,
            context.scope,
            chunk_id=chunk_id,
            version_id=hit.version_id,
            page=hit.page,
            section=hit.section,
            quote=claim.quote,
        )
        return CitationDraft(
            chunk_id=chunk_id,
            document_id=hit.document_id,
            version_id=hit.version_id,
            page=hit.page,
            section=hit.section,
            quote=(claim.quote or "").strip()[:400],
            locator=hit.locator,
            check_status="rejected",
            check_reason=result.reason or "quote_not_found",
        )

    return CitationDraft(
        chunk_id="",
        document_id="",
        version_id="",
        page=None,
        section=None,
        quote=(claim.quote or "").strip()[:400],
        locator="",
        check_status="rejected",
        check_reason="chunk_missing",
    )


def validate(state: dict[str, Any], config) -> dict[str, Any]:
    started = time.perf_counter()
    context = runtime_of(config)
    payload: AnswerPayload = state["payload"]
    hits = state.get("hits", ())

    citations: list[CitationDraft] = []
    rejected: list[CitationDraft] = []
    with context.factory() as session:
        for claim in payload.claims:
            draft = _draft_for_claim(session, context, claim, hits)
            if draft is not None:
                citations.append(draft)
            else:
                rejected.append(_rejected_draft(session, context, claim, hits))

    reason_codes = sorted({draft.check_reason for draft in rejected if draft.check_reason})
    tracer_of(config).operation(
        "validate",
        run_type="chain",
        inputs={"claims": len(payload.claims), "hits": len(hits)},
        outputs={
            "valid": len(citations),
            "rejected": len(rejected),
            "reason_codes": reason_codes,
        },
        duration_ms=elapsed_ms(started),
    )
    return {
        "citations": tuple(citations),
        "rejected": tuple(rejected),
        "steps": record_step(
            state,
            "validate",
            "deterministic",
            "ok",
            started,
            {
                "valid": len(citations),
                "rejected": len(rejected),
                "reasons": reason_codes,
            },
        ),
    }


def route_after_validate(state: dict[str, Any]) -> str:
    if state.get("citations"):
        return "persist"
    payload = state.get("payload")
    claims = payload.claims if payload is not None else []
    tool_evidence = any(item.get("status") == "ok" for item in state.get("tool_results", ()))
    if not claims and tool_evidence:
        return "persist"
    if (state.get("hits") or claims) and not state.get("repaired"):
        return "repair"
    return "abstain"


def repair(state: dict[str, Any], config) -> dict[str, Any]:
    started = time.perf_counter()
    context = runtime_of(config)
    step_count = _consume_step(state, context)
    reasons = [draft.check_reason or "cita inválida" for draft in state.get("rejected", ())]
    plan = plan_prompt(
        question=context.question,
        hits=state.get("hits", ()),
        history=state.get("history", ()),
        settings=context.deps.settings,
        counter=context.deps.token_counter,
        repair_reasons=reasons,
    )
    timeout = _model_timeout(context)
    tracer = tracer_of(config)
    try:
        payload = _call_model(
            context,
            lambda **kwargs: context.deps.generator.generate(
                system=plan.system, user=plan.user, **kwargs
            ),
            timeout,
        )
    except Exception as exc:
        tracer.operation(
            "agent.repair",
            run_type="llm",
            inputs={"model": context.deps.generator.model, "reason_codes": reasons},
            error=type(exc).__name__,
        )
        raise
    usage = getattr(context.deps.generator, "last_usage", None) or {}
    plan_detail = plan.detail()
    tracer.operation(
        "agent.repair",
        run_type="llm",
        inputs={
            "model": context.deps.generator.model,
            "reason_codes": reasons,
            "admitted_tokens": plan_detail.get("admitted_tokens"),
            "history_messages": plan_detail.get("history_messages"),
            "sources": plan_detail.get("sources"),
            "dropped_history_messages": plan_detail.get("dropped_history_messages"),
            "dropped_sources": plan_detail.get("dropped_sources"),
            "limit": plan_detail.get("limit"),
        },
        outputs={
            "claims": len(payload.claims),
            "answer_length": len(payload.answer),
            "missing_info": len(payload.missing_info),
            "recommendations": len(payload.recommendations),
        },
        duration_ms=elapsed_ms(started),
    )
    _check_turn_deadline(context)
    return {
        "payload": payload,
        "hits": plan.hits,
        "repaired": True,
        "step_count": step_count,
        "steps": record_step(
            state,
            "repair",
            "model",
            "ok",
            started,
            {
                "claims": len(payload.claims),
                **plan.detail(),
                "observed_prompt_tokens": usage.get("prompt_tokens"),
            },
        ),
    }


def abstain(state: dict[str, Any], config) -> dict[str, Any]:
    started = time.perf_counter()
    if not state.get("hits"):
        outcome = "insufficient_evidence"
        text = INSUFFICIENT_EVIDENCE_TEXT
    else:
        outcome = "abstained_invalid_citations"
        text = ABSTAINED_CITATIONS_TEXT
    tracer_of(config).operation(
        "abstain",
        run_type="chain",
        inputs={"hits": len(state.get("hits", ())), "rejected": len(state.get("rejected", ()))},
        outputs={"outcome": outcome},
        duration_ms=elapsed_ms(started),
    )
    return {
        "outcome": outcome,
        "answer": text,
        "citations": (),
        "steps": record_step(
            state,
            "abstain",
            "deterministic",
            "ok",
            started,
            {"outcome": outcome, "rejected": len(state.get("rejected", ()))},
        ),
    }


def _save_memory(config) -> str:
    """Guarda la instantánea después del commit; un fallo no rompe la respuesta."""
    memory = memory_of(config)
    if memory is None:
        return "disabled"
    context = runtime_of(config)
    settings = context.deps.settings
    try:
        with context.factory() as session:
            turns = service.load_confirmed_history(
                session,
                context.conversation_id,
                max_messages=settings.history_max_messages,
                max_chars=settings.history_max_chars,
            )
        memory.write(context.conversation_id, turns)
    except Exception:
        return "failed"
    return "saved"


def persist(state: dict[str, Any], config) -> dict[str, Any]:
    started = time.perf_counter()
    context = runtime_of(config)
    payload: AnswerPayload | None = state.get("payload")
    answer_text = (state.get("answer") or (payload.answer if payload else "")).strip()
    citations = state.get("citations", ())
    claims = payload.claims if payload is not None else []
    tool_evidence = any(item.get("status") == "ok" for item in state.get("tool_results", ()))
    if state.get("outcome"):
        outcome = state["outcome"]
    elif citations or (tool_evidence and not claims):
        outcome = "answered"
    else:
        outcome = "insufficient_evidence"
    if not answer_text:
        answer_text = ABSTAINED_CITATIONS_TEXT
        outcome = "abstained_invalid_citations" if state.get("hits") else "insufficient_evidence"

    duration_ms = _turn_duration(context)
    message_id = persist_turn(
        context.factory,
        run_id=context.run_id,
        answer_text=answer_text,
        citations=citations,
        rejected=state.get("rejected", ()),
        tool_calls=state.get("tool_records", ()),
        hits=state.get("hits", ()),
        steps=record_step(state, "persist", "deterministic", "ok", started),
        outcome=outcome,
        duration_ms=duration_ms,
    )
    memory_status = _save_memory(config)
    tracer_of(config).operation(
        "persist",
        run_type="chain",
        inputs={
            "citations": len(citations),
            "rejected": len(state.get("rejected", ())),
            "tool_results": len(state.get("tool_records", ())),
            "hits": len(state.get("hits", ())),
        },
        outputs={
            "outcome": outcome,
            "memory_status": memory_status,
            "answer_length": len(answer_text),
        },
        duration_ms=elapsed_ms(started),
    )
    return {
        "answer_message_id": message_id,
        "persisted": True,
        "outcome": outcome,
        "memory_status": memory_status,
    }


def _turn_duration(context) -> int:
    return elapsed_ms(context.started_perf)


def generation_config(settings) -> GenerationConfig:
    return GenerationConfig(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        num_ctx=settings.generator_num_ctx,
        num_predict=settings.generator_num_predict,
        temperature=settings.generator_temperature,
        seed=settings.generator_seed,
        timeout_seconds=settings.llm_timeout_seconds,
    )


def failure_step(state: dict[str, Any], name: str, code: str) -> tuple[StepRecord, ...]:
    return _append(
        state,
        StepRecord(
            name=name,
            origin="model",
            status="error",
            duration_ms=0,
            detail={"error": code},
        ),
    )


__all__ = [
    "abstain",
    "agent",
    "decide",
    "fail_run",
    "load_memory",
    "load_scope",
    "persist",
    "repair",
    "resolve_source_id",
    "retrieve",
    "route_after_decide",
    "route_after_validate",
    "tools",
    "validate",
]
