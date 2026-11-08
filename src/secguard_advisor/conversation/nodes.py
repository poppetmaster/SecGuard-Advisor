"""Nodos deterministas y de modelo del grafo conversacional."""

from __future__ import annotations

import time
from typing import Any

from secguard_advisor.cases.scope import require_case
from secguard_advisor.conversation.llm import (
    AnswerPayload,
    Claim,
    GenerationConfig,
    RunTimeout,
    elapsed_ms,
)
from secguard_advisor.conversation.persistence import (
    CitationDraft,
    StepRecord,
    fail_run,
    persist_turn,
)
from secguard_advisor.conversation.prompts import (
    SYSTEM_PROMPT,
    build_repair_prompt,
    build_user_prompt,
)
from secguard_advisor.retrieval.citations import check_citation
from secguard_advisor.retrieval.search import RetrievedChunk, search_documents

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


def load_scope(state: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    context = state["context"]
    with context.factory() as session:
        require_case(session, context.scope)
    return {"steps": record_step(state, "load_scope", "deterministic", "ok", started)}


def retrieve(state: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    context = state["context"]
    with context.factory() as session:
        result = search_documents(
            session,
            scope=context.scope,
            query=context.question,
            embedder=context.deps.embedder,
            index=context.deps.index,
            top_k=context.deps.settings.retrieval_top_k,
            min_score=context.deps.settings.retrieval_min_score,
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


def agent(state: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    context = state["context"]
    payload = context.deps.generator.generate(
        system=SYSTEM_PROMPT,
        user=build_user_prompt(context.question, state.get("hits", ())),
    )
    _check_turn_deadline(context)
    return {
        "payload": payload,
        "steps": record_step(
            state, "agent", "model", "ok", started, {"claims": len(payload.claims)}
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


def validate(state: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    context = state["context"]
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

    return {
        "citations": tuple(citations),
        "rejected": tuple(rejected),
        "steps": record_step(
            state,
            "validate",
            "deterministic",
            "ok",
            started,
            {"valid": len(citations), "rejected": len(rejected)},
        ),
    }


def route_after_validate(state: dict[str, Any]) -> str:
    if state.get("citations"):
        return "persist"
    if state.get("hits") and not state.get("repaired"):
        return "repair"
    return "abstain"


def repair(state: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    context = state["context"]
    reasons = [draft.check_reason or "cita inválida" for draft in state.get("rejected", ())]
    payload = context.deps.generator.generate(
        system=SYSTEM_PROMPT,
        user=build_repair_prompt(context.question, state.get("hits", ()), reasons),
    )
    _check_turn_deadline(context)
    return {
        "payload": payload,
        "repaired": True,
        "steps": record_step(
            state, "repair", "model", "ok", started, {"claims": len(payload.claims)}
        ),
    }


def abstain(state: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    if not state.get("hits"):
        outcome = "insufficient_evidence"
        text = INSUFFICIENT_EVIDENCE_TEXT
    else:
        outcome = "abstained_invalid_citations"
        text = ABSTAINED_CITATIONS_TEXT
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


def persist(state: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    context = state["context"]
    payload: AnswerPayload | None = state.get("payload")
    answer_text = (state.get("answer") or (payload.answer if payload else "")).strip()
    citations = state.get("citations", ())
    outcome = state.get("outcome") or ("answered" if citations else "insufficient_evidence")
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
        hits=state.get("hits", ()),
        steps=record_step(state, "persist", "deterministic", "ok", started),
        outcome=outcome,
        duration_ms=duration_ms,
    )
    return {"answer_message_id": message_id, "persisted": True, "outcome": outcome}


def _turn_duration(context) -> int:
    return elapsed_ms(context.started_perf)


def generation_config(settings) -> GenerationConfig:
    return GenerationConfig(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        num_ctx=settings.generator_num_ctx,
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
    "fail_run",
    "load_scope",
    "persist",
    "repair",
    "resolve_source_id",
    "retrieve",
    "route_after_validate",
    "validate",
]
