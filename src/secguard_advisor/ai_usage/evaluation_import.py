"""Importación explícita e idempotente de informes de evaluación."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from secguard_advisor.db.models import (
    AiEvaluation,
    AiEvaluationResult,
    Run,
    utc_now_iso,
)

PROVIDERS = ("ollama", "deepseek", "anthropic")
QUALITY_METHOD = "AI-assisted heuristic; not independent human review"


@dataclass(frozen=True, slots=True)
class ImportReport:
    evaluation_id: str
    created: int
    updated: int
    providers: tuple[str, ...] = field(default_factory=tuple)


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _decimal(value) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _quality(row: dict) -> tuple[Decimal | None, str | None]:
    quality = row.get("quality") or {}
    values = [
        quality.get(key)
        for key in ("accuracy", "relevance", "clarity", "recommendations", "uncertainty")
    ]
    present = [value for value in values if value is not None]
    if not present:
        return None, None
    score = Decimal(str(sum(present) / len(present))).quantize(Decimal("0.01"))
    return score, quality.get("method") or QUALITY_METHOD


def _upsert(
    session: Session,
    *,
    evaluation: AiEvaluation,
    row: dict,
) -> bool:
    provider = row["provider"]
    scenario = row["scenario"]
    existing = session.scalar(
        select(AiEvaluationResult).where(
            AiEvaluationResult.evaluation_id == evaluation.id,
            AiEvaluationResult.provider == provider,
            AiEvaluationResult.scenario == scenario,
        )
    )
    cost = row.get("cost") or {}
    citations = row.get("citations") or []
    usage = row.get("usage") or {}
    quality_score, quality_method = _quality(row)
    run_id = row.get("run_id")
    linked_run = session.get(Run, run_id) if run_id else None
    values = {
        "model": row.get("model") or "",
        "kind": row.get("kind"),
        "executed": row.get("result") != "blocked",
        "result": row.get("result") or "failed",
        "outcome": row.get("outcome"),
        "error_code": row.get("error_code"),
        "duration_ms": row.get("duration_ms"),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "cached_tokens": usage.get("cached_tokens"),
        "usage_source": usage.get("source")
        if usage.get("source") in {"observed", "estimated"}
        else "unavailable",
        "cost_usd": _decimal(cost.get("usd")),
        "cost_status": cost.get("status") or "unknown",
        "tariff_version": cost.get("tariff_version"),
        "citations_emitted": len(citations),
        "citations_valid": sum(1 for item in citations if item.get("check_status") == "valid"),
        "citations_resolvable": sum(1 for item in citations if item.get("resolvable")),
        "findings_match": row.get("findings_match"),
        "abstention_ok": row.get("abstention_ok"),
        "quality_score": quality_score,
        "quality_method": quality_method,
        "manual_review": "none",
        "run_id": linked_run.id if linked_run is not None else None,
        "detail_level": "linked" if linked_run is not None else "aggregate",
    }
    if existing is None:
        session.add(
            AiEvaluationResult(
                evaluation_id=evaluation.id,
                provider=provider,
                scenario=scenario,
                **values,
            )
        )
        return True
    for key, value in values.items():
        setattr(existing, key, value)
    return False


def import_evaluation(
    session: Session,
    evidence_dir: str | Path,
    *,
    name: str | None = None,
) -> ImportReport:
    """Importa ``casos.json`` y ``resultados-<proveedor>.json`` una sola vez.

    No crea ``ai_requests``: los agregados no permiten reconstruir solicitudes.
    """
    root = Path(evidence_dir)
    casos_path = root / "casos.json"
    if not casos_path.exists():
        raise FileNotFoundError(f"No existe el informe congelado en {root}.")
    casos = json.loads(casos_path.read_text(encoding="utf-8"))
    version = casos["version"]
    sha = casos["sha256"]
    import_key = f"{version}:{sha}"
    evaluation = session.scalar(select(AiEvaluation).where(AiEvaluation.import_key == import_key))
    files = []
    created = 0
    updated = 0
    providers = []
    if evaluation is None:
        evaluation = AiEvaluation(
            id=f"eval-{sha[:24]}",
            import_key=import_key,
            name=name or f"Evaluación {version}",
            version=version,
            frozen_at=casos.get("frozen_at"),
            dataset_sha256=sha,
            source="report_import",
            source_path=str(root),
            detail_level="aggregate",
            provenance_json="{}",
            imported_at=utc_now_iso(),
        )
        session.add(evaluation)
        session.flush()
    for provider in PROVIDERS:
        path = root / f"resultados-{provider}.json"
        if not path.exists():
            continue
        providers.append(provider)
        files.append(
            {
                "file": path.name,
                "sha256": _file_sha(path),
            }
        )
        rows = json.loads(path.read_text(encoding="utf-8"))
        for row in rows:
            if _upsert(session, evaluation=evaluation, row=row):
                created += 1
            else:
                updated += 1
    evaluation.detail_level = "aggregate"
    evaluation.provenance_json = json.dumps(
        {
            "files": files,
            "report_version": version,
            "dataset_sha256": sha,
            "frozen_at": casos.get("frozen_at"),
            "imported_at": evaluation.imported_at,
            "detail_level": "aggregate",
            "note": "Los agregados no reconstruyen solicitudes individuales.",
        },
        ensure_ascii=False,
        indent=2,
    )
    session.flush()
    return ImportReport(
        evaluation_id=evaluation.id,
        created=created,
        updated=updated,
        providers=tuple(providers),
    )
