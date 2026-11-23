"""Evaluación funcional de 005: 10 escenarios por proveedor disponible.

Usa una instancia temporal, corpus público oficial y un caso ficticio. No imprime
claves. Respeta los presupuestos existentes y no modifica .env.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.fixtures.corpus import create_case, seed_document
from tests.fixtures.evaluation_005 import (
    CASE_DOCUMENTS,
    FROZEN_AT,
    SCENARIOS,
    SYNTHETIC_FINDINGS,
    VERSION,
    dataset_payload,
    dataset_sha256,
)
from tests.fixtures.findings import seed_findings

from secguard_advisor.ai_config.service import (
    auto_output_tokens,
    resolve_turn_settings,
    save_configuration,
)
from secguard_advisor.cases.external import authorize_case
from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.conversation.memory import open_memory
from secguard_advisor.conversation.providers.context import build_prompt_counter
from secguard_advisor.conversation.providers.cost import reserve_amount
from secguard_advisor.conversation.providers.registry import ProviderRegistry
from secguard_advisor.conversation.turn import execute_turn, start_question_turn
from secguard_advisor.corpus.ingest import ingest_public_corpus
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import (
    Asset,
    Document,
    DocumentChunk,
    Finding,
    Message,
    MessageCitation,
    ProviderBudgetLedger,
    ProviderUsage,
    QualysVulnerability,
    Run,
    RunStep,
    RunToolCall,
)
from secguard_advisor.documents.embedding import OllamaEmbeddingClient
from secguard_advisor.retrieval.index import QdrantIndex
from secguard_advisor.vulnerabilities.service import QualysImportService

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "files"
PROVIDERS = ("ollama", "deepseek", "anthropic")
MODELS = {"ollama": "qwen3.5:9b", "deepseek": "deepseek-flash", "anthropic": "claude-haiku-5-5"}
MAX_OUTPUT_EXTERNAL = 1200


class ProviderBlocked(RuntimeError):
    pass


def _base_settings() -> Settings:
    return Settings()


def _settings(root: Path, base: Settings) -> Settings:
    return Settings(
        _env_file=None,
        storage_dir=root / "storage",
        corpus_dir=Path("data/corpus").resolve(),
        instance_id=f"eval005-{uuid.uuid4().hex[:8]}",
        generation_provider="ollama",
        generation_model="qwen3.5:9b",
        generation_max_output_tokens=auto_output_tokens(base),
        generation_timeout_seconds=90,
        deepseek_api_key=base.deepseek_api_key,
        anthropic_api_key=base.anthropic_api_key,
        external_budget_usd=base.external_budget_usd,
        external_run_budget_usd=base.external_run_budget_usd,
        external_tariff_version=base.external_tariff_version,
    )


def _prepare(root: Path, base: Settings):
    settings = _settings(root, base)
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    embedder = OllamaEmbeddingClient(
        base_url=settings.ollama_base_url,
        model=settings.ollama_embedding_model,
        dimension=settings.embedding_dim,
        context_tokens=settings.embedding_context_tokens,
    )
    index = QdrantIndex(
        url=settings.qdrant_url,
        instance_id=settings.instance_id,
        timeout=settings.qdrant_timeout_seconds,
        storage_dir=settings.storage_dir,
    )
    outcomes = ingest_public_corpus(factory, settings, embedder=embedder, index=index)
    if not all(outcome.status in {"created", "duplicate"} for outcome in outcomes):
        raise RuntimeError("El corpus público no se ingirió correctamente.")
    return settings, factory, embedder, index


def _new_case(factory, provider: str, scenario: dict, embedder, index) -> str:
    with factory() as session:
        case_id = create_case(session, f"Evaluación {provider} {scenario['id']}")
        session.commit()
    if scenario["case_documents"]:
        for document in CASE_DOCUMENTS:
            seed_document(
                factory,
                texts=[document["text"]],
                index=index,
                embedder=embedder,
                case_id=case_id,
                title=document["title"],
            )
    if scenario["findings"]:
        seed_findings(factory, case_id=case_id, findings=list(SYNTHETIC_FINDINGS))
    if scenario["id"] == "S08":
        service = QualysImportService(factory, _settings_for_service(factory))
        content = (FIXTURES / "qualys_synthetic_valid.csv").read_bytes()
        staged = service.stage_import(case_id, "synthetic-eval.csv", content)
        service.confirm_import(case_id, staged.import_record.id)
    return case_id


def _settings_for_service(factory):
    # The service only needs the factory and threshold settings; build a minimal one.
    from secguard_advisor.config import Settings

    return Settings(_env_file=None)


def _expected_synthetic(factory, case_id: str) -> dict:
    with factory() as session:
        rows = session.execute(
            select(Asset.name, func.count())
            .select_from(Finding)
            .join(Asset, Finding.asset_id == Asset.id)
            .where(Finding.case_id == case_id, Finding.severity_label == "High")
            .group_by(Asset.name)
        ).all()
        total = session.scalar(
            select(func.count())
            .select_from(Finding)
            .where(Finding.case_id == case_id, Finding.severity_label == "High")
        )
    return {"total": int(total or 0), "groups": {name: int(count) for name, count in rows}}


def _expected_imported(factory, case_id: str) -> dict:
    with factory() as session:
        rows = session.execute(
            select(QualysVulnerability.asset_label, func.count())
            .where(
                QualysVulnerability.case_id == case_id,
                QualysVulnerability.severity_level == 5,
                QualysVulnerability.exploitability_eval == "positive",
                QualysVulnerability.status_group == "pending_known",
            )
            .group_by(QualysVulnerability.asset_label)
        ).all()
        total = session.scalar(
            select(func.count())
            .select_from(QualysVulnerability)
            .where(
                QualysVulnerability.case_id == case_id,
                QualysVulnerability.severity_level == 5,
                QualysVulnerability.exploitability_eval == "positive",
                QualysVulnerability.status_group == "pending_known",
            )
        )
    return {"total": int(total or 0), "groups": {name: int(count) for name, count in rows}}


def _estimate_external(provider: str, settings: Settings) -> Decimal:
    now = datetime.now(UTC)
    per_call = reserve_amount(
        provider,
        MODELS[provider],
        input_tokens=4000,
        max_output_tokens=MAX_OUTPUT_EXTERNAL,
        at=now,
        tariff_version=settings.external_tariff_version,
    )
    return per_call * 20


def _close(resource) -> None:
    close = getattr(resource, "close", None)
    if callable(close):
        close()


def _collect(factory, scenario: dict, context, result, started: float, expected: dict) -> dict:
    with factory() as session:
        run = session.get(Run, context.run_id)
        answer = session.get(Message, run.answer_message_id) if run.answer_message_id else None
        citations = []
        source_ids = []
        if run.answer_message_id:
            for citation in session.scalars(
                select(MessageCitation).where(MessageCitation.message_id == run.answer_message_id)
            ):
                document = session.get(Document, citation.document_id)
                chunk = session.get(DocumentChunk, citation.chunk_id)
                citations.append(
                    {
                        "document_title": document.title if document else None,
                        "source_id": document.source_id if document else None,
                        "check_status": citation.check_status,
                        "quote": citation.quote,
                        "resolvable": chunk is not None,
                        "literal": bool(chunk and citation.quote in chunk.text),
                    }
                )
                if document and document.source_id:
                    source_ids.append(document.source_id)
        steps = list(
            session.scalars(select(RunStep).where(RunStep.run_id == run.id).order_by(RunStep.seq))
        )
        tools = list(session.scalars(select(RunToolCall).where(RunToolCall.run_id == run.id)))
        usage = {
            "input_tokens": run.usage_input_tokens,
            "output_tokens": run.usage_output_tokens,
            "cached_tokens": run.usage_cached_tokens,
            "source": run.usage_source,
        }
        cost = {
            "status": run.cost_status,
            "usd": str(run.cost_usd) if run.cost_usd is not None else None,
            "tariff_version": run.cost_tariff_version,
        }
        agent = next((step for step in steps if step.name == "agent"), None)
        detail = json.loads(agent.detail_json) if agent and agent.detail_json else {}
        model_steps = [
            {"name": step.name, "duration_ms": step.duration_ms}
            for step in steps
            if step.origin == "model"
        ]
        answer_text = answer.content if answer else ""
        keyword_hits = [
            keyword
            for keyword in scenario["expected"].get("keywords", [])
            if keyword.lower() in answer_text.lower()
        ]
        expected_sources = scenario.get("expected_sources", [])
        citation_titles = [item["document_title"] for item in citations]
        source_hit = (
            any(item in source_ids or item in citation_titles for item in expected_sources)
            if expected_sources
            else True
        )
        findings_match = None
        findings_summary = None
        if scenario["id"] in {"S07", "S08"}:
            matching = [tool for tool in tools if tool.status == "ok"]
            if matching:
                findings_summary = json.loads(matching[0].result_summary_json or "{}")
                groups = {
                    group["key"]: group["count"] for group in findings_summary.get("groups", [])
                }
                findings_match = (
                    findings_summary.get("total") == expected["total"]
                    and groups == expected["groups"]
                )
        outcome = run.outcome
        if scenario.get("follow_up_of"):
            # conversation continuity is verified by the same case/memory and history_messages > 0.
            followup_ok = int(detail.get("history_messages") or 0) > 0
        else:
            followup_ok = True
        abstention_ok = (
            outcome in {"insufficient_evidence", "abstained_invalid_citations"}
            if scenario["expected"].get("abstention")
            else None
        )
        structure_ok = bool(agent is not None and detail)
        approved = False
        if scenario["id"] == "S08" and run.generator_provider != "ollama":
            approved = False
        elif scenario["id"] == "S09":
            approved = bool(abstention_ok and not citations)
        elif scenario["id"] in {"S07", "S08"}:
            approved = bool(
                result.status == "succeeded" and outcome == "answered" and findings_match
            )
        elif scenario["id"] == "S10":
            approved = bool(
                result.status == "succeeded"
                and outcome == "answered"
                and structure_ok
                and citations
                and int(detail.get("recommendations") or 0) >= 1
                and ("limit" in answer_text.lower() or "falta" in answer_text.lower())
            )
        else:
            approved = bool(
                result.status == "succeeded"
                and outcome == "answered"
                and citations
                and source_hit
                and keyword_hits
            )
        quality = _quality(
            scenario, answer_text, keyword_hits, citations, detail, findings_match, abstention_ok
        )
        return {
            "scenario": scenario["id"],
            "kind": scenario["kind"],
            "provider": run.generator_provider,
            "model": run.generator_model,
            "identity": run.generator_identity,
            "run_id": run.id,
            "status": run.status,
            "outcome": outcome,
            "error_code": run.error_code,
            "result": "blocked"
            if run.error_code == "external_tool_blocked"
            else ("approved" if approved else "failed"),
            "duration_ms": run.duration_ms,
            "model_calls": len(model_steps),
            "model_steps": model_steps,
            "repairs": sum(1 for step in steps if step.name == "repair"),
            "tool_calls": [
                {"tool": tool.tool_name, "status": tool.status, "origin": tool.origin}
                for tool in tools
            ],
            "usage": usage,
            "cost": cost,
            "citations": citations,
            "source_hit": source_hit,
            "keywords_hit": keyword_hits,
            "structure_ok": structure_ok,
            "findings_match": findings_match,
            "findings_summary": findings_summary,
            "expected": expected,
            "followup_ok": followup_ok,
            "abstention_ok": abstention_ok,
            "quality": quality,
            "answer": answer_text[:1200],
        }


def _quality(
    scenario, answer, keyword_hits, citations, detail, findings_match, abstention_ok
) -> dict:
    expected_keywords = scenario["expected"].get("keywords", [])
    if scenario["id"] in {"S07", "S08"}:
        accuracy = 2 if findings_match else 0
    elif scenario["id"] == "S09":
        accuracy = 2 if abstention_ok else 0
    else:
        accuracy = (
            2
            if expected_keywords and len(keyword_hits) == len(expected_keywords)
            else (1 if keyword_hits else 0)
        )
    relevance = 2 if accuracy == 2 else (1 if answer else 0)
    clarity = 2 if len(answer) >= 80 else (1 if answer else 0)
    recommendations = (
        2
        if int(detail.get("recommendations") or 0) >= 2
        else (1 if int(detail.get("recommendations") or 0) == 1 else 0)
    )
    uncertainty = (
        2
        if scenario["id"] == "S09" and abstention_ok
        else (1 if "limit" in answer.lower() or "falta" in answer.lower() else 0)
    )
    return {
        "accuracy": accuracy,
        "relevance": relevance,
        "clarity": clarity,
        "recommendations": recommendations,
        "uncertainty": uncertainty,
        "method": "AI-assisted heuristic; not independent human review",
    }


def _summarize(rows: list[dict], provider: str) -> dict:
    executed = [row for row in rows if row["result"] != "blocked"]
    approved = [row for row in rows if row["result"] == "approved"]
    blocked = [row for row in rows if row["result"] == "blocked"]
    failed = [row for row in rows if row["result"] == "failed"]
    durations = [row["duration_ms"] for row in executed if row["duration_ms"] is not None]
    costs = [
        Decimal(row["cost"]["usd"])
        for row in executed
        if row["cost"]["status"] == "calculated" and row["cost"]["usd"] is not None
    ]
    quality = [
        sum(
            row["quality"][key]
            for key in ("accuracy", "relevance", "clarity", "recommendations", "uncertainty")
        )
        / 5
        for row in executed
    ]
    return {
        "provider": provider,
        "executed": len(executed),
        "approved": len(approved),
        "failed": len(failed),
        "blocked": len(blocked),
        "success_rate": round(len(approved) / len(executed), 4) if executed else 0,
        "median_latency_ms": int(statistics.median(durations)) if durations else None,
        "mean_latency_ms": int(sum(durations) / len(durations)) if durations else None,
        "max_latency_ms": max(durations) if durations else None,
        "input_tokens": sum(row["usage"]["input_tokens"] or 0 for row in executed),
        "output_tokens": sum(row["usage"]["output_tokens"] or 0 for row in executed),
        "total_cost_usd": str(sum(costs)) if costs else None,
        "avg_cost_usd": str(sum(costs) / len(executed)) if costs and executed else None,
        "structure_rate": round(
            sum(1 for row in executed if row["structure_ok"]) / len(executed), 4
        )
        if executed
        else 0,
        "citation_valid_rate": round(
            sum(
                1
                for row in executed
                if row["citations"]
                and all(c["literal"] and c["resolvable"] for c in row["citations"])
            )
            / len(executed),
            4,
        )
        if executed
        else 0,
        "abstention_correct": sum(1 for row in executed if row["abstention_ok"] is True),
        "quality_avg": round(sum(quality) / len(quality), 2) if quality else None,
    }


def run_provider(provider: str, root: Path, base: Settings, embedder, index):
    settings = _settings(root, base)
    # The shared DB is created by _prepare; only the active profile changes.
    with create_session_factory(create_engine_for_url(settings.database_url))() as session:
        save_configuration(
            session,
            settings,
            provider=provider,
            model=MODELS[provider],
            max_output_tokens=auto_output_tokens(base)
            if provider == "ollama"
            else MAX_OUTPUT_EXTERNAL,
            timeout_seconds=90,
        )
        session.commit()
    with create_session_factory(create_engine_for_url(settings.database_url))() as session:
        turn_settings = resolve_turn_settings(session, settings)
    generator = ProviderRegistry(turn_settings).create()
    counter = build_prompt_counter(turn_settings)
    memory = open_memory(settings.checkpoints_path)
    factory = create_session_factory(create_engine_for_url(settings.database_url))
    cases: dict[str, str] = {}
    expected_by_case: dict[str, dict] = {}
    rows = []
    try:
        for scenario in SCENARIOS:
            if scenario.get("follow_up_of"):
                case_id = cases[scenario["follow_up_of"]]
            else:
                case_id = _new_case(factory, provider, scenario, embedder, index)
                cases[scenario["id"]] = case_id
            if provider != "ollama":
                with factory() as session:
                    authorize_case(
                        session,
                        case_id=case_id,
                        scope="fictional_case",
                        authorized_by="Evaluación 005",
                    )
                    session.commit()
            expected = {}
            if scenario["id"] == "S07":
                expected = _expected_synthetic(factory, case_id)
            elif scenario["id"] == "S08":
                expected = _expected_imported(factory, case_id)
            expected_by_case[scenario["id"]] = expected
            started = time.perf_counter()
            context = start_question_turn(
                factory,
                turn_settings,
                scope=CaseScope(case_id=case_id),
                question=scenario["question"],
                generator=generator,
                embedder=embedder,
                index=index,
                token_counter=counter,
            )
            result = execute_turn(context, memory=memory)
            rows.append(_collect(factory, scenario, context, result, started, expected))
    finally:
        _close(generator)
        _close(counter)
        memory.close()
    return rows, expected_by_case


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--providers", default="ollama,deepseek,anthropic")
    args = parser.parse_args()
    base = _base_settings()
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    providers = [item.strip() for item in args.providers.split(",") if item.strip()]
    with tempfile.TemporaryDirectory(prefix="eval005-") as directory:
        root = Path(directory)
        settings, factory, embedder, index = _prepare(root, base)
        try:
            casos = {
                "version": VERSION,
                "frozen_at": FROZEN_AT,
                "sha256": dataset_sha256(),
                "dataset": dataset_payload(),
                "expected": {},
                "budget_estimate": {},
                "budget": {
                    "global_usd": str(base.external_budget_usd),
                    "run_usd": str(base.external_run_budget_usd),
                    "tariff_version": base.external_tariff_version,
                },
            }
            for provider in providers:
                if provider != "ollama":
                    estimate = _estimate_external(provider, settings)
                    casos["budget_estimate"][provider] = str(estimate)
                    if estimate > base.external_budget_usd:
                        casos.setdefault("blocked", {})[provider] = "presupuesto insuficiente"
                        continue
                try:
                    rows, expected = run_provider(provider, root, base, embedder, index)
                except Exception as exc:
                    casos.setdefault("blocked", {})[provider] = f"{type(exc).__name__}: {exc}"
                    continue
                casos["expected"][provider] = expected
                (output / f"resultados-{provider}.json").write_text(
                    json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
        finally:
            _close(embedder)
            _close(index)
        # Budget consumption from the evaluation DB.
        with factory() as session:
            spent = session.scalar(
                select(func.coalesce(func.sum(ProviderBudgetLedger.settled_usd), 0))
            )
            usage_cost = session.scalar(select(func.coalesce(func.sum(ProviderUsage.cost_usd), 0)))
        casos["budget"]["spent_ledger_usd"] = str(spent or 0)
        casos["budget"]["spent_usage_usd"] = str(usage_cost or 0)
        casos["budget"]["remaining_usd"] = str(
            base.external_budget_usd - Decimal(str(usage_cost or 0))
        )
        (output / "casos.json").write_text(
            json.dumps(casos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(
            json.dumps(
                {
                    "providers": {
                        name: str(output / f"resultados-{name}.json") for name in providers
                    },
                    "budget": casos["budget"],
                    "blocked": casos.get("blocked", {}),
                },
                ensure_ascii=False,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
