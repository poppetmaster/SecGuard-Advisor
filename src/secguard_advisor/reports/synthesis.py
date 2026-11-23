"""Optional factual/synthesized narrative for the executive report."""

from __future__ import annotations

import contextlib
import copy
import json
import re
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from secguard_advisor.ai_config.service import load_view, resolve_turn_settings
from secguard_advisor.config import Settings
from secguard_advisor.conversation.llm import InvalidModelOutput, ModelTimeout, ModelUnavailable
from secguard_advisor.conversation.providers.base import ProviderError
from secguard_advisor.conversation.providers.registry import ProviderRegistry
from secguard_advisor.db.models import (
    AiRequest,
    ExternalProcessingAuthorization,
    Run,
    utc_now_iso,
)
from secguard_advisor.reports.errors import ReportError

ALLOWED_IDENTIFIER_PATTERNS = (
    re.compile(r"CVE-\d{4}-\d{4,}"),
    re.compile(r"QID\s*\d+", re.IGNORECASE),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"\b(?:v|versi[oó]n|version|informe)\s*[A-Za-z0-9-]+\b", re.IGNORECASE),
)


class SynthesisSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(description="Resumen breve en español, sin cifras libres")
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
    summary: SynthesisSummary
    focus: list[SynthesisLine] = Field(default_factory=list)
    recommendations: list[SynthesisLine] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


@dataclass(frozen=True, slots=True)
class SynthesisResult:
    status: str
    payload: dict[str, Any]
    run_id: str | None
    error_code: str | None = None


def _factual_payload(dataset: dict[str, Any], reason: str) -> dict[str, Any]:
    critical = dataset["cards"]["critical_pending"]["value"]
    high = dataset["cards"]["high_pending"]["value"]
    focus = []
    if critical:
        focus.append(
            {
                "text": "Hay registros pendientes de severidad crítica que requieren revisión.",
                "basis": "csv_fact",
                "claim_refs": ["cards.critical_pending.value"],
                "evidence_refs": [],
                "caveat": None,
            }
        )
    if high:
        focus.append(
            {
                "text": "Hay registros pendientes de severidad alta que requieren seguimiento.",
                "basis": "csv_fact",
                "claim_refs": ["cards.high_pending.value"],
                "evidence_refs": [],
                "caveat": None,
            }
        )
    return {
        "summary": {
            "text": (
                "Informe factual generado desde la instantánea confirmada. "
                f"{reason} Las cifras se calculan en SQLite y no dependen de una síntesis."
            ),
            "claim_refs": ["cards.pending.value"],
        },
        "focus": focus,
        "recommendations": [],
        "limitations": [
            *dataset.get("limitations", []),
            "Sin síntesis de IA: no se generaron explicaciones ni recomendaciones nuevas.",
        ],
    }


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


def _validate_line(dataset: dict[str, Any], line: SynthesisLine) -> dict[str, Any]:
    if not line.text.strip():
        raise ReportError("synthesis_invalid", "Una afirmación de la síntesis está vacía.")
    if _has_free_number(line.text):
        raise ReportError(
            "synthesis_invalid",
            "La síntesis contiene una cifra libre que no proviene de una referencia estructurada.",
        )
    for ref in line.claim_refs:
        _resolve_ref(dataset, ref)
    if line.basis == "csv_fact" and not line.claim_refs:
        raise ReportError("synthesis_invalid", "Un hecho del CSV exige una referencia de métrica.")
    if line.basis == "documentary" and not line.evidence_refs:
        raise ReportError("synthesis_invalid", "Una referencia documental exige una cita.")
    basis = line.basis
    caveat = line.caveat
    if basis == "documentary":
        # The citation validator can prove existence/identity, not semantic entailment.
        basis = "agent_proposal"
        caveat = (
            "Referencia documental; respaldo semántico no verificado. Se presenta como propuesta."
        )
    return {
        "text": line.text.strip(),
        "basis": basis,
        "claim_refs": list(line.claim_refs),
        "evidence_refs": list(line.evidence_refs),
        "caveat": caveat,
    }


def validate_payload(dataset: dict[str, Any], payload: ReportSynthesisPayload) -> dict[str, Any]:
    if not payload.summary.text.strip():
        raise ReportError("synthesis_invalid", "El resumen de la síntesis está vacío.")
    if _has_free_number(payload.summary.text):
        raise ReportError("synthesis_invalid", "El resumen contiene una cifra libre.")
    for ref in payload.summary.claim_refs:
        _resolve_ref(dataset, ref)
    return {
        "summary": {
            "text": payload.summary.text.strip(),
            "claim_refs": list(payload.summary.claim_refs),
        },
        "focus": [_validate_line(dataset, item) for item in payload.focus],
        "recommendations": [_validate_line(dataset, item) for item in payload.recommendations],
        "limitations": [item.strip() for item in payload.limitations if item.strip()]
        or list(dataset.get("limitations", [])),
    }


def _prompt_dataset(dataset: dict[str, Any], *, external: bool) -> dict[str, Any]:
    value = copy.deepcopy(dataset)
    value.pop("case", None)
    value["assets_top"]["items"] = [
        {k: item[k] for k in ("alias", "critical", "high", "total")}
        for item in value["assets_top"]["items"]
    ]
    if external:
        value["limitations"] = [
            "Datos agregados de una instantánea ficticia o pública; sin nombres internos."
        ]
    return value


SYSTEM_PROMPT = """Eres un redactor técnico defensivo. Devuelve JSON que cumpla el esquema.
No inventes cifras: usa exclusivamente claim_refs a métricas del dataset; las cifras se renderizan
después. Puedes usar identificadores QID, CVE, versión o fechas. Distingue hechos (csv_fact),
referencias documentales (documentary) y propuestas (agent_proposal). Una cita no demuestra
respaldo semántico; si no tienes respaldo comprobado, usa agent_proposal con caveat. No inventes
remediaciones ni prioridades P1-P4. No incluyas nombres internos, IP ni filas crudas."""


def _create_run(session: Session, settings: Settings, case_id: str) -> Run:
    run = Run(
        case_id=case_id,
        conversation_id=None,
        kind="report",
        status="running",
        generator_model=settings.provider_model,
        generator_provider=settings.generation_provider,
        cost_status="not_applicable" if settings.generation_provider == "ollama" else "unknown",
        generator_max_output_tokens=settings.provider_max_output_tokens,
        generator_timeout_seconds=settings.provider_timeout_seconds,
        generator_num_ctx=settings.provider_context_window,
        generator_temperature=settings.generator_temperature,
        generator_seed=settings.generator_seed,
        embedding_model=settings.ollama_embedding_model,
        embedding_dim=settings.embedding_dim,
        prompt_version="report-synthesis-v1",
        started_at=utc_now_iso(),
    )
    session.add(run)
    session.flush()
    return run


def _finish_run(
    session: Session,
    run: Run,
    *,
    status: str,
    outcome: str,
    usage: dict | None,
    error_code: str | None = None,
) -> None:
    run.status = status
    run.outcome = outcome
    run.finished_at = utc_now_iso()
    run.error_code = error_code
    if usage:
        run.usage_input_tokens = usage.get("input_tokens")
        run.usage_output_tokens = usage.get("output_tokens")
        run.usage_cached_tokens = usage.get("cached_tokens")
        run.usage_cache_write_tokens = usage.get("cache_write_tokens")
        run.usage_source = usage.get("source")
    usage_source = (usage or {}).get("source")
    if usage_source not in {"observed", "estimated"}:
        usage_source = "unavailable"
    session.add(
        AiRequest(
            run_id=run.id,
            operation="generate",
            attempt_no=1,
            provider=run.generator_provider,
            model=run.generator_model,
            started_at=run.started_at,
            finished_at=run.finished_at,
            status=("completed" if status == "succeeded" and error_code is None else "error"),
            duration_ms=(usage or {}).get("duration_ms"),
            input_tokens=(usage or {}).get("input_tokens"),
            output_tokens=(usage or {}).get("output_tokens"),
            cached_tokens=(usage or {}).get("cached_tokens"),
            cache_write_tokens=(usage or {}).get("cache_write_tokens"),
            reasoning_tokens=(usage or {}).get("reasoning_tokens"),
            usage_source=usage_source,
            cost_status=run.cost_status,
            error_code=error_code,
            created_at=run.started_at,
        )
    )


def synthesize_report(
    session: Session,
    settings: Settings,
    *,
    case_id: str,
    dataset: dict[str, Any],
    enabled: bool,
    generator: Any | None = None,
) -> SynthesisResult:
    """Try optional synthesis; always return a usable factual payload on failure."""
    if not enabled:
        return SynthesisResult(
            "not_requested", _factual_payload(dataset, "No se solicitó síntesis."), None
        )

    turn_settings = resolve_turn_settings(session, settings)
    external = turn_settings.generation_provider != "ollama"
    if external:
        view = load_view(session, settings)
        authorization = session.scalar(
            select(ExternalProcessingAuthorization).where(
                ExternalProcessingAuthorization.case_id == case_id,
                ExternalProcessingAuthorization.revoked_at.is_(None),
            )
        )
        if view.external_blocked or authorization is None:
            return SynthesisResult(
                "unavailable",
                _factual_payload(
                    dataset, "No hay autorización o presupuesto para el proveedor externo."
                ),
                None,
                "provider_not_authorized",
            )

    run = _create_run(session, turn_settings, case_id)
    session.flush()
    provider = generator or ProviderRegistry(turn_settings).create(resolve_digest=False)
    usage = None
    try:
        payload = provider.generate_structured(
            system=SYSTEM_PROMPT,
            user=json.dumps(_prompt_dataset(dataset, external=external), ensure_ascii=False),
            schema=ReportSynthesisPayload,
            timeout_seconds=turn_settings.provider_timeout_seconds,
        )
        validated = validate_payload(dataset, payload)
        usage = getattr(provider, "last_usage", None)
        run.generator_identity = getattr(provider, "identity", None)
        _finish_run(session, run, status="succeeded", outcome="report_ready", usage=usage)
        return SynthesisResult("completed", validated, run.id)
    except (ReportError, InvalidModelOutput, ModelTimeout, ModelUnavailable, ProviderError) as exc:
        usage = getattr(provider, "last_usage", None)
        code = getattr(exc, "code", None) or "synthesis_invalid"
        _finish_run(
            session,
            run,
            status=("timeout" if isinstance(exc, ModelTimeout) else "failed"),
            outcome="report_factual",
            usage=usage,
            error_code=code,
        )
        return SynthesisResult(
            "failed", _factual_payload(dataset, "La síntesis no se completó."), run.id, code
        )
    except Exception:  # pragma: no cover - provider boundary
        usage = getattr(provider, "last_usage", None)
        _finish_run(
            session,
            run,
            status="failed",
            outcome="report_factual",
            usage=usage,
            error_code="synthesis_invalid",
        )
        return SynthesisResult(
            "failed",
            _factual_payload(dataset, "La síntesis no se completó."),
            run.id,
            "synthesis_invalid",
        )
    finally:
        if generator is None:
            with contextlib.suppress(Exception):
                provider.close()
