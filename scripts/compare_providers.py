"""Comparación reproducible de proveedores (005, T035-T039).

No envía datos a proveedores externos reales sin presupuesto explícito. El modo
``mock`` usa transporte HTTP simulado y se rotula como simulado. El corpus es
ficticio y se usa almacenamiento temporal.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.fixtures.corpus import create_case, seed_document
from tests.fixtures.fakes import FakeEmbedder
from tests.fixtures.provider_comparison import (
    DATASET_VERSION,
    DOCUMENTS,
    FROZEN_AT,
    QUESTIONS,
    dataset_sha256,
)
from tests.fixtures.qdrant import embedded_index

from secguard_advisor.cases.external import authorize_case
from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.conversation.memory import open_memory
from secguard_advisor.conversation.providers.anthropic import AnthropicGenerator
from secguard_advisor.conversation.providers.context import EstimatedPromptCounter
from secguard_advisor.conversation.providers.deepseek import DeepSeekGenerator
from secguard_advisor.conversation.providers.registry import ProviderRegistry
from secguard_advisor.conversation.tokenizer import load_prompt_counter
from secguard_advisor.conversation.turn import execute_turn, start_question_turn
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import (
    Document,
    Message,
    MessageCitation,
    Run,
    RunStep,
    RunToolCall,
)
from secguard_advisor.documents.embedding import OllamaEmbeddingClient


class SkippedProvider(RuntimeError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def _settings(root: Path, provider: str, transport: str) -> Settings:
    overrides = {
        "storage_dir": root / "storage",
        "generation_provider": provider,
        "generation_max_output_tokens": 512,
        "generation_timeout_seconds": 90.0,
    }
    if transport == "mock":
        overrides.update(
            {
                "generation_model": (
                    "deepseek-flash" if provider == "deepseek" else "claude-haiku-5-5"
                ),
                "deepseek_api_key": "mock",
                "anthropic_api_key": "mock",
                "external_budget_usd": Decimal("1"),
                "external_run_budget_usd": Decimal("1"),
            }
        )
    return Settings(_env_file=None, **overrides)


def _mock_client(provider: str) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/count_tokens"):
            return httpx.Response(200, json={"input_tokens": 100})
        body = json.loads(request.content)
        system = ""
        if provider == "deepseek":
            system = body["messages"][0]["content"]
        else:
            system = body.get("system", "")
        if "clasificador" in system.lower() or "ToolDecision" in system:
            content = json.dumps({"use_findings": False, "arguments": {}})
        else:
            content = json.dumps(
                {
                    "answer": "Respuesta simulada de comparación.",
                    "claims": [],
                    "missing_info": [],
                    "recommendations": ["Revisar la evidencia."],
                }
            )
        if provider == "deepseek":
            return httpx.Response(
                200,
                json={
                    "model": "deepseek-flash",
                    "choices": [{"message": {"content": content}}],
                    "usage": {
                        "prompt_tokens": 100,
                        "completion_tokens": 20,
                        "prompt_cache_hit_tokens": 0,
                    },
                },
            )
        return httpx.Response(
            200,
            json={
                "model": "claude-haiku-5-5",
                "content": [{"type": "text", "text": content}],
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 20,
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                },
            },
        )

    return httpx.Client(transport=httpx.MockTransport(handler), timeout=12.5)


def _prepare(root: Path, provider: str, transport: str):
    settings = _settings(root, provider, transport)
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    if provider == "ollama":
        embedder = OllamaEmbeddingClient(
            base_url=settings.ollama_base_url,
            model=settings.ollama_embedding_model,
            dimension=settings.embedding_dim,
            context_tokens=settings.embedding_context_tokens,
        )
        generator = ProviderRegistry(settings).create()
        token_counter = load_prompt_counter(settings.provider_model)
        retrieval = "ollama-embeddinggemma"
    elif transport == "mock":
        embedder = FakeEmbedder()
        client = _mock_client(provider)
        if provider == "deepseek":
            generator = DeepSeekGenerator(settings, client=client)
        else:
            generator = AnthropicGenerator(settings, client=client)
        token_counter = EstimatedPromptCounter()
        retrieval = "fake-embeddings"
    else:
        if settings.external_budget_usd <= 0 or settings.external_run_budget_usd <= 0:
            raise SkippedProvider("Sin presupuesto externo aprobado (external_budget_usd=0).")
        try:
            generator = ProviderRegistry(settings).create()
        except Exception as exc:
            raise SkippedProvider(
                f"Credencial o configuración externa no disponible: {type(exc).__name__}."
            ) from exc
        embedder = OllamaEmbeddingClient(
            base_url=settings.ollama_base_url,
            model=settings.ollama_embedding_model,
            dimension=settings.embedding_dim,
            context_tokens=settings.embedding_context_tokens,
        )
        token_counter = SuggestedCounter(settings)
        retrieval = "ollama-embeddinggemma"

    index = embedded_index(root)
    with factory() as session:
        case_id = create_case(session, "Comparación 005")
        if provider != "ollama":
            authorize_case(
                session,
                case_id=case_id,
                scope="fictional_case",
                authorized_by=(
                    "Comparación simulada" if transport == "mock" else "Comparación real"
                ),
            )
        session.commit()
    for document in DOCUMENTS:
        seed_document(
            factory,
            texts=[document["text"]],
            index=index,
            embedder=embedder,
            case_id=case_id,
            title=document["title"],
        )
    memory = open_memory(settings.checkpoints_path)
    return settings, factory, index, embedder, generator, token_counter, memory, case_id, retrieval


class SuggestedCounter:
    """Contador estimado para un proveedor externo real si no se inyecta otro."""

    def __init__(self, settings: Settings) -> None:
        self._counter = EstimatedPromptCounter(
            settings.external_estimate_chars_per_token,
            settings.external_estimate_overhead_tokens,
        )

    def count(self, system: str, user: str) -> int:
        return self._counter.count(system, user)

    def describe(self) -> dict:
        return self._counter.describe()


def _step_detail(session, run_id: str) -> dict:
    steps = list(
        session.scalars(select(RunStep).where(RunStep.run_id == run_id).order_by(RunStep.seq))
    )
    agent = next((step for step in reversed(steps) if step.name == "agent"), None)
    detail = json.loads(agent.detail_json) if agent and agent.detail_json else {}
    model_steps = [
        {"name": step.name, "duration_ms": step.duration_ms}
        for step in steps
        if step.origin == "model"
    ]
    return {"detail": detail, "model_steps": model_steps}


def _run_question(
    factory, settings, index, embedder, generator, token_counter, memory, case_id, item
):
    started = time.perf_counter()
    context = start_question_turn(
        factory,
        settings,
        scope=CaseScope(case_id=case_id),
        question=item["question"],
        generator=generator,
        embedder=embedder,
        index=index,
        token_counter=token_counter,
    )
    result = execute_turn(context, memory=memory)
    wall_ms = int((time.perf_counter() - started) * 1000)
    with factory() as session:
        run = session.get(Run, context.run_id)
        answer = session.get(Message, run.answer_message_id) if run.answer_message_id else None
        citations = []
        if run.answer_message_id:
            for citation in session.scalars(
                select(MessageCitation).where(
                    MessageCitation.message_id == run.answer_message_id,
                    MessageCitation.check_status == "valid",
                )
            ):
                document = session.get(Document, citation.document_id)
                citations.append(
                    {
                        "document_title": document.title if document else None,
                        "quote": citation.quote[:160],
                        "check_status": citation.check_status,
                    }
                )
        tools = list(session.scalars(select(RunToolCall).where(RunToolCall.run_id == run.id)))
        structure = _step_detail(session, run.id)
        return {
            "id": item["id"],
            "question": item["question"],
            "expected_title": item["expected_title"],
            "must_cite": item["must_cite"],
            "expect_abstention": item["expect_abstention"],
            "status": run.status,
            "outcome": run.outcome,
            "error_code": run.error_code,
            "duration_ms": run.duration_ms,
            "wall_ms": wall_ms,
            "answer": answer.content[:400] if answer else None,
            "citations": citations,
            "citation_hit": any(
                citation["document_title"] == item["expected_title"] for citation in citations
            )
            if item["expected_title"]
            else False,
            "tools": [
                {"tool": tool.tool_name, "status": tool.status, "origin": tool.origin}
                for tool in tools
            ],
            "structure": structure,
            "usage": {
                "input_tokens": run.usage_input_tokens,
                "output_tokens": run.usage_output_tokens,
                "cached_tokens": run.usage_cached_tokens,
                "source": run.usage_source,
            },
            "cost": {
                "status": run.cost_status,
                "usd": str(run.cost_usd) if run.cost_usd is not None else None,
                "tariff_version": run.cost_tariff_version,
            },
            "turn_result": asdict(result),
        }


def _summarize(results: list[dict]) -> dict:
    answerable = [item for item in results if item["must_cite"]]
    abstentions = [item for item in results if item["expect_abstention"]]
    durations = [item["duration_ms"] for item in results if item["duration_ms"] is not None]
    costs = [
        Decimal(item["cost"]["usd"])
        for item in results
        if item["cost"]["status"] == "calculated" and item["cost"]["usd"] is not None
    ]
    return {
        "turns": len(results),
        "answered": sum(1 for item in results if item["outcome"] == "answered"),
        "citations_total": sum(len(item["citations"]) for item in results),
        "expected_citations_hit": sum(1 for item in answerable if item["citation_hit"]),
        "expected_citations_total": len(answerable),
        "abstentions_expected": len(abstentions),
        "abstentions_observed": sum(
            1
            for item in abstentions
            if item["outcome"] in {"insufficient_evidence", "abstained_invalid_citations"}
        ),
        "avg_duration_ms": int(sum(durations) / len(durations)) if durations else None,
        "recommendations_total": sum(
            int(((item.get("structure") or {}).get("detail") or {}).get("recommendations") or 0)
            for item in results
        ),
        "missing_info_total": sum(
            int(((item.get("structure") or {}).get("detail") or {}).get("missing_info") or 0)
            for item in results
        ),
        "total_cost_usd": str(sum(costs)) if costs else None,
        "cost_unknown_turns": sum(1 for item in results if item["cost"]["status"] == "unknown"),
        "semantic_evaluation": "not_performed",
    }


def _markdown(report: dict) -> str:
    lines = [
        f"# Comparación de proveedores — {report['provider']}",
        "",
        f"- Fecha: {report['executed_at']}",
        f"- Conjunto: `{report['dataset']['version']}` (`{report['dataset']['sha256']}`)",
        f"- Transporte: **{report['transport']}**",
        f"- Modelo: `{report['model']}`",
        f"- Recuperación: {report['retrieval']}",
        "",
        "## Métricas",
        "",
        "| Métrica | Valor |",
        "|---|---|",
    ]
    for key, value in report["metrics"].items():
        lines.append(f"| {key} | {value} |")
    lines.extend(
        [
            "",
            "## Preguntas",
            "",
            "| ID | Estado | Outcome | Citas | Esperada | ms | Costo |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for item in report["results"]:
        lines.append(
            f"| {item['id']} | {item['status']} | {item['outcome']} | "
            f"{len(item['citations'])} | {item['citation_hit']} | {item['duration_ms']} | "
            f"{item['cost']['status']} |"
        )
    lines.extend(
        [
            "",
            "La evaluación semántica no se realizó. Las comprobaciones son automáticas.",
        ]
    )
    return "\n".join(lines) + "\n"


def run(provider: str, transport: str, root: Path) -> dict:
    settings, factory, index, embedder, generator, token_counter, memory, case_id, retrieval = (
        _prepare(root, provider, transport)
    )
    try:
        results = [
            _run_question(
                factory,
                settings,
                index,
                embedder,
                generator,
                token_counter,
                memory,
                case_id,
                item,
            )
            for item in QUESTIONS
        ]
        report = {
            "provider": provider,
            "model": getattr(generator, "model", settings.provider_model),
            "transport": transport,
            "retrieval": retrieval,
            "executed_at": datetime.now(UTC).isoformat(),
            "dataset": {
                "version": DATASET_VERSION,
                "frozen_at": FROZEN_AT,
                "sha256": dataset_sha256(),
                "questions": len(QUESTIONS),
            },
            "settings": {
                "provider": settings.generation_provider,
                "model": settings.provider_model,
                "max_output_tokens": settings.provider_max_output_tokens,
                "timeout_seconds": settings.provider_timeout_seconds,
                "context_window": settings.provider_context_window,
                "external_budget_usd": str(settings.external_budget_usd),
                "tariff_version": settings.external_tariff_version,
            },
            "results": results,
            "metrics": _summarize(results),
            "limitations": [
                "Evaluación semántica no realizada.",
                "El corpus es ficticio y no representa al usuario.",
            ],
        }
        return report
    finally:
        generator.close()
        embedder.close()
        index.close()
        memory.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--provider", choices=("ollama", "deepseek", "anthropic", "all"), required=True
    )
    parser.add_argument("--transport", choices=("real", "mock"), default="real")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, default=None)
    args = parser.parse_args()
    providers = ["ollama", "deepseek", "anthropic"] if args.provider == "all" else [args.provider]
    reports = []
    with tempfile.TemporaryDirectory(prefix="005-compare-") as directory:
        root = Path(directory)
        for provider in providers:
            if provider == "ollama" and args.transport == "mock":
                reports.append({"provider": provider, "skipped": "mock no aplica a Ollama"})
                continue
            try:
                report = run(provider, args.transport, root / provider)
            except SkippedProvider as exc:
                reports.append(
                    {
                        "provider": provider,
                        "transport": args.transport,
                        "skipped": exc.reason,
                        "executed_at": datetime.now(UTC).isoformat(),
                    }
                )
                continue
            except Exception as exc:
                if provider == "ollama":
                    raise
                reports.append(
                    {
                        "provider": provider,
                        "transport": args.transport,
                        "skipped": f"Configuración externa no disponible: {type(exc).__name__}.",
                        "executed_at": datetime.now(UTC).isoformat(),
                    }
                )
                continue
            reports.append(report)
    payload = reports[0] if len(reports) == 1 else {"reports": reports}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        if len(reports) == 1 and "metrics" in reports[0]:
            args.markdown.write_text(_markdown(reports[0]), encoding="utf-8")
        else:
            args.markdown.write_text(
                "# Comparación\n\n" + json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
