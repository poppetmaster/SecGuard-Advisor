"""Optional synthesis with 005 controls, deterministic facts and strict validation."""

from __future__ import annotations

import contextlib
import copy
import json
import re
import time
import unicodedata
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, sessionmaker

from secguard_advisor.ai_config.service import resolve_turn_settings
from secguard_advisor.ai_usage.telemetry import record_ai_request
from secguard_advisor.cases.external import (
    ExternalProcessingBlocked,
    ensure_external_allowed,
)
from secguard_advisor.config import Settings
from secguard_advisor.conversation.budget import (
    ContextBudgetExceeded,
    ContextBudgetUnavailable,
    check_prompt,
)
from secguard_advisor.conversation.concurrency import GenerationSlot
from secguard_advisor.conversation.llm import InvalidModelOutput, ModelTimeout, ModelUnavailable
from secguard_advisor.conversation.providers.base import ProviderError
from secguard_advisor.conversation.providers.context import (
    EstimatedPromptCounter,
    build_prompt_counter,
)
from secguard_advisor.conversation.providers.cost import CostResult
from secguard_advisor.conversation.providers.registry import ProviderRegistry
from secguard_advisor.db.models import (
    Document,
    DocumentChunk,
    DocumentVersion,
    ProviderUsage,
    QualysVulnerability,
    Run,
    utc_now_iso,
)
from secguard_advisor.evidence.budget import (
    begin_call,
    reconcile_call,
    release_call,
    settle_call,
)
from secguard_advisor.reports.errors import ReportError

ALLOWED_IDENTIFIER_PATTERNS = (
    re.compile(r"CVE-\d{4}-\d{4,}"),
    re.compile(r"QID\s*\d+", re.IGNORECASE),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"\b(?:v|versi[oó]n|version|informe)\s*[A-Za-z0-9-]+\b", re.IGNORECASE),
)
IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
INTERNAL_HOST_PATTERN = re.compile(
    r"\b[a-z0-9][a-z0-9.-]*\.(?:local|internal|corp|lan)\b", re.IGNORECASE
)
ABSENCE_PATTERN = re.compile(
    r"\b(sin|no\s+hay|no\s+se\s+identificaron|ninguna|ninguno|cero)\b", re.IGNORECASE
)


class SynthesisSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(
        default="", description="Se ignora; los hechos se renderizan desde el dataset"
    )
    claim_refs: list[str] = Field(default_factory=list)


class SynthesisLine(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(description="Afirmación o recomendación en español")
    basis: Literal["csv_fact", "documentary", "agent_proposal"] = Field(
        description="Procedencia declarada"
    )
    claim_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    caveat: str | None = None


class ReportSynthesisPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: SynthesisSummary = Field(default_factory=SynthesisSummary)
    focus: list[SynthesisLine] = Field(default_factory=list)
    recommendations: list[SynthesisLine] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


@dataclass(frozen=True, slots=True)
class SynthesisResult:
    status: str
    payload: dict[str, Any]
    run_id: str | None
    error_code: str | None = None


def _normalized(value: str) -> str:
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").lower()


def _has_free_number(text: str) -> bool:
    remainder = text
    for pattern in ALLOWED_IDENTIFIER_PATTERNS:
        remainder = pattern.sub(" ", remainder)
    return bool(re.search(r"\d", remainder))


def _resolve_ref(dataset: dict[str, Any], ref: str) -> Any:
    current: Any = dataset
    for part in ref.split("."):
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError) as exc:
                raise ReportError("synthesis_invalid", "Referencia de métrica inválida.") from exc
        elif isinstance(current, dict) and part in current:
            current = current[part]
        else:
            raise ReportError("synthesis_invalid", "Referencia de métrica inválida.")
    return current


def _forbidden_labels(dataset: dict[str, Any]) -> list[str]:
    labels = [
        item.get("internal_label", "")
        for item in dataset.get("assets_top", {}).get("items", [])
        if item.get("internal_label")
    ]
    if not dataset.get("content_policy", {}).get("include_case_title", False):
        labels.append(dataset.get("case", {}).get("title", ""))
    return [label for label in labels if label]


def _validate_text(dataset: dict[str, Any], text: str, forbidden: set[str] | None = None) -> None:
    if not text.strip():
        raise ReportError("synthesis_invalid", "Un campo de texto de la síntesis está vacío.")
    if _has_free_number(text):
        raise ReportError(
            "synthesis_invalid",
            "La síntesis contiene una cifra libre que no proviene de una referencia estructurada.",
        )
    if IP_PATTERN.search(text) or INTERNAL_HOST_PATTERN.search(text):
        raise ReportError("synthesis_invalid", "La síntesis contiene una IP o un nombre interno.")
    normalized = _normalized(text)
    for label in forbidden if forbidden is not None else _forbidden_labels(dataset):
        if _normalized(label) in normalized:
            raise ReportError("synthesis_invalid", "La síntesis contiene un nombre interno.")


def _contradicts(dataset: dict[str, Any], text: str) -> bool:
    normalized = _normalized(text)
    if not ABSENCE_PATTERN.search(normalized):
        return False
    cards = dataset["cards"]
    checks = (
        (("crític", "critic"), cards["critical_pending"]["value"]),
        (("alt",), cards["high_pending"]["value"]),
        (("pendient", "vulnerabilidad"), cards["pending"]["value"]),
        (("explotabilidad",), cards["exploitability_positive_pending"]["value"]),
        (("malware",), cards["malware_positive_pending"]["value"]),
        (("ambos",), cards["both_positive_pending"]["value"]),
        (("fixed",), cards["fixed"]["value"]),
        (("revisi",), cards["manual_review"]["value"]),
    )
    return any(value > 0 and any(term in normalized for term in terms) for terms, value in checks)


def _resolve_evidence(
    session: Session, case_id: str, refs: list[str], *, allow_public: bool
) -> None:
    for ref in refs:
        if not ref.startswith("chunk:"):
            raise ReportError("synthesis_invalid", "Referencia documental no reconocida.")
        chunk_id = ref.split(":", 1)[1]
        statement = (
            select(DocumentChunk.id)
            .join(DocumentVersion, DocumentVersion.id == DocumentChunk.version_id)
            .join(Document, Document.id == DocumentVersion.document_id)
            .where(DocumentChunk.id == chunk_id)
        )
        scope = [and_(Document.origin == "case_evidence", Document.case_id == case_id)]
        if allow_public:
            scope.append(Document.origin == "public_corpus")
        statement = statement.where(or_(*scope))
        if session.scalar(statement) is None:
            raise ReportError(
                "synthesis_invalid",
                "Una referencia documental no existe o está fuera del alcance permitido.",
            )


def _validate_line(
    session: Session,
    dataset: dict[str, Any],
    line: SynthesisLine,
    *,
    case_id: str,
    allow_public: bool,
    forbidden: set[str],
) -> dict[str, Any]:
    _validate_text(dataset, line.text, forbidden)
    if _contradicts(dataset, line.text):
        raise ReportError("synthesis_invalid", "La síntesis contradice una métrica del dataset.")
    for ref in line.claim_refs:
        _resolve_ref(dataset, ref)
    if line.caveat:
        _validate_text(dataset, line.caveat, forbidden)
    if line.evidence_refs:
        _resolve_evidence(session, case_id, line.evidence_refs, allow_public=allow_public)
    if line.basis == "documentary" and not line.evidence_refs:
        raise ReportError("synthesis_invalid", "Una referencia documental exige una cita.")
    caveat = line.caveat
    if line.basis == "documentary":
        caveat = (
            "Referencia documental validada por existencia; respaldo semántico no verificado. "
            "Se presenta como propuesta."
        )
    return {
        "text": line.text.strip(),
        "basis": "agent_proposal",
        "claim_refs": list(line.claim_refs),
        "evidence_refs": list(line.evidence_refs),
        "caveat": caveat,
    }


def validate_payload(
    session: Session,
    dataset: dict[str, Any],
    payload: ReportSynthesisPayload,
    *,
    case_id: str,
    allow_public: bool = True,
) -> dict[str, Any]:
    forbidden = set(_forbidden_labels(dataset))
    snapshot_id = dataset.get("snapshot", {}).get("import_id")
    if snapshot_id:
        forbidden.update(
            session.scalars(
                select(QualysVulnerability.asset_label).where(
                    QualysVulnerability.case_id == case_id,
                    QualysVulnerability.import_id == snapshot_id,
                )
            )
        )
    forbidden.discard("Sin activo")
    if payload.summary.text:
        _validate_text(dataset, payload.summary.text, forbidden)
        if _contradicts(dataset, payload.summary.text):
            raise ReportError("synthesis_invalid", "El resumen contradice una métrica del dataset.")
        for ref in payload.summary.claim_refs:
            _resolve_ref(dataset, ref)
    for item in payload.focus:
        _validate_line(
            session, dataset, item, case_id=case_id, allow_public=allow_public, forbidden=forbidden
        )
    recommendations = [
        _validate_line(
            session, dataset, item, case_id=case_id, allow_public=allow_public, forbidden=forbidden
        )
        for item in payload.recommendations
    ]
    for item in payload.limitations:
        _validate_text(dataset, item, forbidden)
        if _contradicts(dataset, item):
            raise ReportError(
                "synthesis_invalid", "Una limitación contradice una métrica del dataset."
            )
    return {
        "summary": _deterministic_summary(dataset),
        "focus": _deterministic_focus(dataset),
        "recommendations": recommendations,
        "limitations": _deterministic_limitations(dataset, synthesized=True),
    }


def _deterministic_summary(dataset: dict[str, Any]) -> dict[str, Any]:
    return {
        "text": (
            "Informe factual de la instantánea confirmada. Las tarjetas y gráficas resumen "
            "los registros pendientes, críticos, altos, activos e indicadores; las "
            "limitaciones explican la cobertura y los datos faltantes."
        ),
        "claim_refs": ["cards.pending.value"],
    }


def _deterministic_focus(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    cards = dataset["cards"]
    items = []
    if cards["critical_pending"]["value"]:
        items.append(
            (
                "Hay registros pendientes de severidad crítica que requieren revisión.",
                "cards.critical_pending.value",
            )
        )
    if cards["high_pending"]["value"]:
        items.append(
            (
                "Hay registros pendientes de severidad alta que requieren seguimiento.",
                "cards.high_pending.value",
            )
        )
    if cards["pending"]["value"] and not items:
        items.append(
            (
                "Hay registros pendientes en la instantánea confirmada.",
                "cards.pending.value",
            )
        )
    if cards["exploitability_positive_pending"]["value"]:
        items.append(
            (
                "Hay registros pendientes con explotabilidad positiva.",
                "cards.exploitability_positive_pending.value",
            )
        )
    if cards["malware_positive_pending"]["value"]:
        items.append(
            (
                "Hay registros pendientes con malware asociado positivo.",
                "cards.malware_positive_pending.value",
            )
        )
    if cards["both_positive_pending"]["value"]:
        items.append(
            (
                "Hay registros pendientes con ambos indicadores positivos.",
                "cards.both_positive_pending.value",
            )
        )
    if cards["fixed"]["value"]:
        items.append(
            (
                "Fixed se conserva como antecedente histórico, no como remediación pendiente.",
                "cards.fixed.value",
            )
        )
    if cards["manual_review"]["value"]:
        items.append(
            (
                "Hay registros que requieren revisión de estado o indicadores.",
                "cards.manual_review.value",
            )
        )
    return [
        {
            "text": text,
            "basis": "csv_fact",
            "claim_refs": [ref],
            "evidence_refs": [],
            "caveat": None,
        }
        for text, ref in items
    ]


def _deterministic_limitations(dataset: dict[str, Any], *, synthesized: bool) -> list[str]:
    values = list(dataset.get("limitations", []))
    values.append(
        "Síntesis de IA completada; las recomendaciones son propuestas del agente."
        if synthesized
        else "Sin síntesis de IA: no se generaron explicaciones ni recomendaciones nuevas."
    )
    return values


def factual_payload(dataset: dict[str, Any], reason: str) -> dict[str, Any]:
    summary = _deterministic_summary(dataset)
    summary["text"] = f"{summary['text']} {reason}"
    return {
        "summary": summary,
        "focus": _deterministic_focus(dataset),
        "recommendations": [],
        "limitations": _deterministic_limitations(dataset, synthesized=False),
    }


def _prompt_dataset(dataset: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(dataset)
    value.pop("case", None)
    value["assets_top"]["items"] = [
        {key: item[key] for key in ("alias", "critical", "high", "total")}
        for item in value["assets_top"]["items"]
    ]
    return value


SYSTEM_PROMPT = """Eres un redactor técnico defensivo. Devuelve JSON que cumpla el esquema.
El resumen y los focos se generan desde el dataset; dejalos vacíos o breves. Las recomendaciones son
propuestas del agente y deben llevar basis agent_proposal, salvo referencias documentales reales.
No inventes cifras: usa exclusivamente claim_refs a métricas del dataset; las cifras se renderizan
después. Puedes usar identificadores QID, CVE, versión o fechas. No incluyas IP, nombres internos,
nombres de activos ni filas crudas. Una cita no demuestra respaldo semántico; si no puedes
verificarla, no la incluyas. No inventes remediaciones ni prioridades P1-P4."""


def _new_run(
    factory: sessionmaker[Session],
    settings: Settings,
    case_id: str,
    *,
    authorization_id: str | None,
) -> str:
    with factory() as session:
        run = Run(
            case_id=case_id,
            conversation_id=None,
            kind="report",
            status="running",
            generator_model=settings.provider_model,
            generator_provider=settings.generation_provider,
            cost_status=(
                "not_applicable" if settings.generation_provider == "ollama" else "unknown"
            ),
            generator_max_output_tokens=settings.provider_max_output_tokens,
            generator_timeout_seconds=settings.provider_timeout_seconds,
            generator_num_ctx=settings.provider_context_window,
            generator_temperature=settings.generator_temperature,
            generator_seed=settings.generator_seed,
            embedding_model=settings.ollama_embedding_model,
            embedding_dim=settings.embedding_dim,
            prompt_version="report-synthesis-v1",
            external_authorization_id=authorization_id,
            started_at=utc_now_iso(),
        )
        session.add(run)
        session.commit()
        return run.id


def _finish_run(
    factory: sessionmaker[Session],
    run_id: str,
    *,
    status: str,
    outcome: str,
    error_code: str | None,
    usage: dict | None,
    cost: CostResult,
) -> None:
    with factory() as session:
        run = session.get(Run, run_id)
        if run is None:
            return
        run.status = status
        run.outcome = outcome
        run.error_code = error_code
        run.finished_at = utc_now_iso()
        run.generator_identity = getattr(run, "generator_identity", None)
        if usage:
            run.usage_input_tokens = usage.get("input_tokens")
            run.usage_output_tokens = usage.get("output_tokens")
            run.usage_cached_tokens = usage.get("cached_tokens")
            run.usage_cache_write_tokens = usage.get("cache_write_tokens")
            run.usage_source = usage.get("source")
        if cost.status == "calculated":
            run.cost_status = "calculated"
            run.cost_usd = cost.usd
            run.cost_tariff_version = cost.tariff_version
        elif cost.status == "not_applicable":
            run.cost_status = "not_applicable"
        else:
            run.cost_status = "unknown"
            run.cost_usd = None
        session.add(
            ProviderUsage(
                run_id=run_id,
                attempt_no=1,
                operation="generate",
                provider=run.generator_provider,
                model=run.generator_model,
                input_tokens=(usage or {}).get("input_tokens"),
                output_tokens=(usage or {}).get("output_tokens"),
                cached_tokens=(usage or {}).get("cached_tokens"),
                cache_write_tokens=(usage or {}).get("cache_write_tokens"),
                usage_source=(usage or {}).get("source") or "unknown",
                duration_ms=(usage or {}).get("duration_ms"),
                cost_usd=cost.usd,
                cost_status=cost.status,
                tariff_version=cost.tariff_version,
            )
        )
        record_ai_request(
            session,
            run_id=run_id,
            operation="generate",
            attempt_no=1,
            provider=run.generator_provider,
            model=run.generator_model,
            started_at=run.started_at,
            duration_ms=(usage or {}).get("duration_ms"),
            usage=usage,
            cost=cost,
            status=(
                "completed" if status == "succeeded" else "error" if status == "failed" else status
            ),
            error_code=error_code,
        )
        session.commit()


def _failure_cost(provider: str, reason: str) -> CostResult:
    if provider == "ollama":
        return CostResult("not_applicable", None, None, {"reason": "local"})
    return CostResult("unknown", None, None, {"reason": reason})


def synthesize_report(
    factory: sessionmaker[Session],
    settings: Settings,
    *,
    case_id: str,
    dataset: dict[str, Any],
    enabled: bool,
    generator: Any | None = None,
    counter: Any | None = None,
    generation_slot: GenerationSlot | None = None,
) -> SynthesisResult:
    """Run synthesis with 005 gates; always return a factual payload on failure."""
    if not enabled:
        return SynthesisResult(
            "not_requested", factual_payload(dataset, "No se solicitó síntesis."), None
        )

    if generation_slot is not None and not generation_slot.acquire(timeout=0):
        return SynthesisResult(
            "unavailable",
            factual_payload(dataset, "Ya hay una generación en curso."),
            None,
            "generation_busy",
        )
    try:
        with factory() as session:
            turn_settings = resolve_turn_settings(session, settings)
        external = turn_settings.generation_provider != "ollama"
        authorization = None
        if external:
            with factory() as session:
                try:
                    authorization = ensure_external_allowed(
                        session, case_id=case_id, provider=turn_settings.generation_provider
                    )
                except ExternalProcessingBlocked:
                    return SynthesisResult(
                        "unavailable",
                        factual_payload(
                            dataset,
                            "No hay autorización externa vigente; "
                            "se conserva el informe factual local.",
                        ),
                        None,
                        "external_processing_blocked",
                    )
            if (
                authorization.scope != "fictional_case"
                or dataset.get("snapshot", {}).get("provenance") != "synthetic_public"
                or not dataset.get("case", {}).get("is_synthetic")
                or not dataset.get("case", {}).get("synthetic_notice")
            ):
                return SynthesisResult(
                    "unavailable",
                    factual_payload(
                        dataset,
                        "El contenido no acredita procedencia ficticia o pública; "
                        "no se envía al proveedor externo.",
                    ),
                    None,
                    "external_content_blocked",
                )

        run_id = _new_run(
            factory,
            turn_settings,
            case_id,
            authorization_id=(authorization.id if authorization is not None else None),
        )
        provider_name = turn_settings.generation_provider
        model_name = turn_settings.provider_model
        prompt = _prompt_dataset(dataset)
        user_prompt = json.dumps(prompt, ensure_ascii=False)
        prompt_counter = counter
        if prompt_counter is None:
            prompt_counter = (
                EstimatedPromptCounter(
                    turn_settings.external_estimate_chars_per_token,
                    turn_settings.external_estimate_overhead_tokens,
                )
                if generator is not None
                else build_prompt_counter(turn_settings)
            )
        try:
            admitted = check_prompt(
                system=SYSTEM_PROMPT,
                user=user_prompt,
                settings=turn_settings,
                counter=prompt_counter,
            )
        except (ContextBudgetExceeded, ContextBudgetUnavailable) as exc:
            close = getattr(prompt_counter, "close", None)
            if close:
                with contextlib.suppress(Exception):
                    close()
            code = (
                "context_budget_unavailable"
                if isinstance(exc, ContextBudgetUnavailable)
                else "context_budget_exceeded"
            )
            _finish_run(
                factory,
                run_id,
                status="failed",
                outcome="report_factual",
                error_code=code,
                usage=None,
                cost=_failure_cost(provider_name, code),
            )
            return SynthesisResult(
                "failed",
                factual_payload(dataset, "La síntesis excede el contexto permitido."),
                run_id,
                code,
            )
        close = getattr(prompt_counter, "close", None)
        if close:
            with contextlib.suppress(Exception):
                close()

        reservation = None
        if external:
            with factory() as session:
                try:
                    reservation = begin_call(
                        session,
                        settings=turn_settings,
                        run_id=run_id,
                        attempt_no=1,
                        provider=provider_name,
                        model=model_name,
                        input_tokens=max(1, admitted),
                        max_output_tokens=turn_settings.provider_max_output_tokens,
                    )
                    session.commit()
                except Exception as exc:
                    code = getattr(exc, "code", "budget_exceeded")
                    _finish_run(
                        factory,
                        run_id,
                        status="failed",
                        outcome="report_factual",
                        error_code=code,
                        usage=None,
                        cost=_failure_cost(provider_name, code),
                    )
                    return SynthesisResult(
                        "failed",
                        factual_payload(dataset, "No hay saldo de presupuesto externo disponible."),
                        run_id,
                        code,
                    )

        started = time.perf_counter()
        provider = None
        try:
            provider = generator or ProviderRegistry(turn_settings).create(resolve_digest=False)
            payload = provider.generate_structured(
                system=SYSTEM_PROMPT,
                user=user_prompt,
                schema=ReportSynthesisPayload,
                timeout_seconds=turn_settings.provider_timeout_seconds,
            )
            usage = getattr(provider, "last_usage", None) or {}
            if usage.get("duration_ms") is None:
                usage["duration_ms"] = int((time.perf_counter() - started) * 1000)
            with factory() as session:
                validated = validate_payload(
                    session,
                    dataset,
                    payload,
                    case_id=case_id,
                    allow_public=not external,
                )
            cost = CostResult("not_applicable", None, None, {"reason": "local"})
            if reservation is not None:
                with factory() as session:
                    cost = settle_call(
                        session,
                        reservation,
                        provider=provider_name,
                        model=model_name,
                        input_tokens=usage.get("input_tokens"),
                        output_tokens=usage.get("output_tokens"),
                        cached_tokens=usage.get("cached_tokens"),
                        cache_write_tokens=usage.get("cache_write_tokens"),
                        tariff_version=turn_settings.external_tariff_version,
                    )
                    session.commit()
            _finish_run(
                factory,
                run_id,
                status="succeeded",
                outcome="report_ready",
                error_code=None,
                usage=usage,
                cost=cost,
            )
            return SynthesisResult("completed", validated, run_id)
        except (
            ReportError,
            InvalidModelOutput,
            ModelTimeout,
            ModelUnavailable,
            ProviderError,
        ) as exc:
            usage = getattr(provider, "last_usage", None) if provider is not None else None
            cost = _failure_cost(provider_name, getattr(exc, "code", "synthesis_error"))
            if reservation is not None:
                with factory() as session:
                    if (
                        usage
                        and usage.get("input_tokens") is not None
                        and usage.get("output_tokens") is not None
                    ):
                        cost = settle_call(
                            session,
                            reservation,
                            provider=provider_name,
                            model=model_name,
                            input_tokens=usage.get("input_tokens"),
                            output_tokens=usage.get("output_tokens"),
                            cached_tokens=usage.get("cached_tokens"),
                            cache_write_tokens=usage.get("cache_write_tokens"),
                            tariff_version=turn_settings.external_tariff_version,
                        )
                    elif provider is None:
                        release_call(session, reservation)
                    else:
                        reconcile_call(session, reservation)
                    session.commit()
            code = getattr(exc, "code", "synthesis_invalid")
            _finish_run(
                factory,
                run_id,
                status=("timeout" if isinstance(exc, ModelTimeout) else "failed"),
                outcome="report_factual",
                error_code=code,
                usage=usage,
                cost=cost,
            )
            return SynthesisResult(
                "failed", factual_payload(dataset, "La síntesis no se completó."), run_id, code
            )
        except Exception:
            usage = getattr(provider, "last_usage", None) if provider is not None else None
            cost = _failure_cost(provider_name, "synthesis_error")
            if reservation is not None:
                with factory() as session:
                    if provider is None:
                        release_call(session, reservation)
                    else:
                        reconcile_call(session, reservation)
                    session.commit()
            _finish_run(
                factory,
                run_id,
                status="failed",
                outcome="report_factual",
                error_code="synthesis_error",
                usage=usage,
                cost=cost,
            )
            return SynthesisResult(
                "failed",
                factual_payload(dataset, "La síntesis no se completó."),
                run_id,
                "synthesis_error",
            )
        finally:
            if provider is not None and generator is None:
                with contextlib.suppress(Exception):
                    provider.close()
    finally:
        if generation_slot is not None:
            generation_slot.release()
