"""Aceptación real: Ollama, embeddings, corpus oficial, caso sintético y herramienta.

No usa almacenamiento del usuario. El directorio se elige con
`SECGUARD_ACCEPTANCE_DIR` o, en su defecto, con el `tmp_path` de pytest.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select
from tests.fixtures.corpus import create_case
from tests.fixtures.real_corpus import real_embedder

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.conversation.llm import GenerationConfig, ModelUnavailable, OllamaGenerator
from secguard_advisor.conversation.memory import open_memory
from secguard_advisor.conversation.retry import start_retry_turn
from secguard_advisor.conversation.tokenizer import load_prompt_counter
from secguard_advisor.conversation.turn import execute_turn, start_question_turn
from secguard_advisor.conversation.views import conversation_view
from secguard_advisor.corpus.ingest import ingest_public_corpus
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import (
    Asset,
    Document,
    DocumentVersion,
    Finding,
    Message,
    MessageCitation,
    Run,
    RunStep,
    RunToolCall,
)
from secguard_advisor.documents.service import ingest_document
from secguard_advisor.documents.validation import validate_bytes
from secguard_advisor.retrieval.index import ChromaIndex
from secguard_advisor.retrieval.review import review_citation
from secguard_advisor.seed.demo import seed_demo

pytestmark = pytest.mark.integration

POLICY = (
    "# Política de respaldo\n\n"
    "La organización realiza copias de seguridad cifradas cada 24 horas y prueba la restauración "
    "trimestralmente. El responsable de infraestructura conserva el registro de cada prueba.\n"
)
CORPUS_QUESTION = "¿Cuáles son las seis funciones centrales del NIST Cybersecurity Framework 2.0?"
FOLLOWUP_QUESTION = "¿Y cómo se relaciona eso con la gestión de riesgos de IA?"
CASE_QUESTION = "¿Cada cuánto se prueba la restauración de las copias de seguridad?"
FINDINGS_QUESTION = "¿Cuántos hallazgos de severidad High están registrados? Agrúpalos por activo."
OUT_OF_SCOPE = "¿Cuál es la capital de Francia?"


class FailingGenerator:
    """Falla de forma controlada para producir un intento reintentable."""

    model = "fake-failure"
    digest = None

    def decide(self, *, system: str, user: str, timeout_seconds=None):
        raise ModelUnavailable("fallo inducido para el reintento")

    def generate(self, *, system: str, user: str, timeout_seconds=None):
        raise ModelUnavailable("fallo inducido para el reintento")


def _generator(settings: Settings) -> OllamaGenerator:
    generator = OllamaGenerator(
        GenerationConfig(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            num_ctx=settings.generator_num_ctx,
            num_predict=settings.generator_num_predict,
            temperature=settings.generator_temperature,
            seed=settings.generator_seed,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    )
    generator.digest = generator.resolve_digest()
    return generator


def _ask(factory, settings, *, case_id: str, question: str, generator, embedder, index, memory):
    context = start_question_turn(
        factory,
        settings,
        scope=CaseScope(case_id=case_id),
        question=question,
        generator=generator,
        embedder=embedder,
        index=index,
        token_counter=load_prompt_counter(settings.ollama_model),
    )
    result = execute_turn(context, memory=memory)
    return context, result


def _turn_facts(factory, run_id: str, question: str) -> dict:
    with factory() as session:
        run = session.get(Run, run_id)
        answer = session.get(Message, run.answer_message_id) if run.answer_message_id else None
        citations = (
            list(
                session.scalars(
                    select(MessageCitation).where(
                        MessageCitation.message_id == run.answer_message_id,
                        MessageCitation.check_status == "valid",
                    )
                )
            )
            if run.answer_message_id
            else []
        )
        steps = list(
            session.scalars(select(RunStep).where(RunStep.run_id == run.id).order_by(RunStep.seq))
        )
        tools = list(
            session.scalars(
                select(RunToolCall).where(RunToolCall.run_id == run.id).order_by(RunToolCall.seq)
            )
        )
        budgets = []
        for step in steps:
            if step.detail_json:
                detail = json.loads(step.detail_json)
                if "admitted_tokens" in detail:
                    budgets.append(
                        {
                            "step": step.name,
                            "admitted_tokens": detail.get("admitted_tokens"),
                            "observed_prompt_tokens": detail.get("observed_prompt_tokens"),
                            "limit": detail.get("limit"),
                        }
                    )
        return {
            "question": question,
            "run_id": run.id,
            "status": run.status,
            "outcome": run.outcome,
            "duration_ms": run.duration_ms,
            "model": run.generator_model,
            "digest": run.generator_digest,
            "prompt_version": run.prompt_version,
            "answer": answer.content if answer else None,
            "citations": [
                {
                    "id": citation.id,
                    "message_id": citation.message_id,
                    "document_id": citation.document_id,
                    "chunk_id": citation.chunk_id,
                    "page": citation.page,
                    "locator": citation.locator,
                    "quote": citation.quote[:160],
                }
                for citation in citations
            ],
            "tools": [
                {
                    "tool": tool.tool_name,
                    "origin": tool.origin,
                    "status": tool.status,
                    "arguments": json.loads(tool.arguments_json),
                    "summary": json.loads(tool.result_summary_json)
                    if tool.result_summary_json
                    else None,
                }
                for tool in tools
            ],
            "budget": budgets,
            "trace_status": run.trace_status,
            "trace_id": run.trace_id,
            "trace_url": run.trace_url,
        }


def test_real_acceptance_journey(tmp_path: Path) -> None:
    base = Path(os.environ.get("SECGUARD_ACCEPTANCE_DIR") or tmp_path)
    base.mkdir(parents=True, exist_ok=True)
    settings = Settings(
        storage_dir=base / "storage",
        corpus_dir=Path("data/corpus").resolve(),
        reviewer_name="Aceptación de prueba",
    )
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)

    embedder = real_embedder(settings)
    index = ChromaIndex(settings.chroma_dir)
    memory = open_memory(settings.checkpoints_path)
    generator = _generator(settings)
    summary: dict = {
        "executed_at": datetime.now(UTC).isoformat(),
        "storage": str(base / "storage"),
        "model": settings.ollama_model,
        "digest": generator.digest,
        "project": settings.langsmith_project,
        "turns": [],
    }

    try:
        with factory() as session:
            report = seed_demo(session)
            session.commit()
            case_id = report.case_id
            summary["case_id"] = case_id
            summary["seed_checksum"] = report.checksum
            summary["seed_findings"] = report.findings

        outcomes = ingest_public_corpus(factory, settings, embedder=embedder, index=index)
        assert all(outcome.status in {"created", "duplicate"} for outcome in outcomes)
        with factory() as session:
            public_documents = list(
                session.scalars(select(Document).where(Document.origin == "public_corpus"))
            )
            summary["corpus"] = [
                {
                    "source_id": document.source_id,
                    "title": document.title,
                    "version": (
                        session.get(DocumentVersion, document.current_version_id).declared_version
                        if document.current_version_id
                        else None
                    ),
                }
                for document in public_documents
            ]
        assert len(public_documents) == 4

        upload = validate_bytes(
            "politica-respaldo.md", POLICY.encode("utf-8"), settings.max_upload_bytes
        )
        case_outcome = ingest_document(
            factory,
            settings,
            scope_key=f"case:{case_id}",
            case_id=case_id,
            origin="case_evidence",
            source_id=None,
            title="Política de respaldo",
            upload=upload,
            embedder=embedder,
            index=index,
            declared_version="v1",
            store_original_file=False,
        )
        assert case_outcome.status in {"created", "duplicate"}

        ctx1, result1 = _ask(
            factory,
            settings,
            case_id=case_id,
            question=CASE_QUESTION,
            generator=generator,
            embedder=embedder,
            index=index,
            memory=memory,
        )
        assert result1.status == "succeeded"
        assert result1.outcome == "answered", (
            "la pregunta sobre la evidencia sintética del caso no produjo citas"
        )
        facts1 = _turn_facts(factory, ctx1.run_id, CASE_QUESTION)
        assert facts1["citations"]
        assert facts1["budget"]
        measured = [budget for budget in facts1["budget"] if budget["limit"] is not None]
        assert measured
        for budget in measured:
            assert budget["admitted_tokens"] <= budget["limit"]
        summary["turns"].append(facts1)

        ctx2, result2 = _ask(
            factory,
            settings,
            case_id=case_id,
            question=CORPUS_QUESTION,
            generator=generator,
            embedder=embedder,
            index=index,
            memory=memory,
        )
        assert result2.status == "succeeded"
        assert result2.outcome == "answered", (
            "la pregunta del corpus no produjo una respuesta con citas"
        )
        facts2 = _turn_facts(factory, ctx2.run_id, CORPUS_QUESTION)
        assert facts2["citations"]
        summary["turns"].append(facts2)

        ctx3, result3 = _ask(
            factory,
            settings,
            case_id=case_id,
            question=FOLLOWUP_QUESTION,
            generator=generator,
            embedder=embedder,
            index=index,
            memory=memory,
        )
        assert result3.status == "succeeded"
        with factory() as session:
            messages = list(
                session.scalars(
                    select(Message)
                    .where(Message.conversation_id == ctx1.conversation_id)
                    .order_by(Message.seq)
                )
            )
        assert len(messages) == 6
        summary["turns"].append(_turn_facts(factory, ctx3.run_id, FOLLOWUP_QUESTION))

        ctx4, result4 = _ask(
            factory,
            settings,
            case_id=case_id,
            question=FINDINGS_QUESTION,
            generator=generator,
            embedder=embedder,
            index=index,
            memory=memory,
        )
        assert result4.status == "succeeded"
        assert result4.outcome == "answered"
        facts4 = _turn_facts(factory, ctx4.run_id, FINDINGS_QUESTION)
        assert facts4["tools"] and facts4["tools"][0]["origin"] == "model_requested"
        assert facts4["tools"][0]["status"] == "ok"
        with factory() as session:
            expected_total = session.scalar(
                select(func.count())
                .select_from(Finding)
                .where(Finding.case_id == case_id, Finding.severity_label == "High")
            )
            expected_groups = dict(
                session.execute(
                    select(Asset.name, func.count())
                    .select_from(Finding)
                    .join(Asset, Finding.asset_id == Asset.id)
                    .where(Finding.case_id == case_id, Finding.severity_label == "High")
                    .group_by(Asset.name)
                ).all()
            )
        tool_summary = facts4["tools"][0]["summary"]
        assert tool_summary["total"] == expected_total
        assert {group["key"]: group["count"] for group in tool_summary["groups"]} == expected_groups
        summary["findings"] = {"total": expected_total, "groups": expected_groups}
        summary["turns"].append(facts4)

        ctx5, result5 = _ask(
            factory,
            settings,
            case_id=case_id,
            question=OUT_OF_SCOPE,
            generator=generator,
            embedder=embedder,
            index=index,
            memory=memory,
        )
        assert result5.status == "succeeded"
        assert result5.outcome in {"insufficient_evidence", "abstained_invalid_citations"}
        facts5 = _turn_facts(factory, ctx5.run_id, OUT_OF_SCOPE)
        assert not facts5["citations"]
        summary["turns"].append(facts5)

        # Revisión humana declarada, no autenticación.
        first_citation = facts1["citations"][0]
        with factory() as session:
            reviewed = review_citation(
                session,
                CaseScope(case_id=case_id),
                message_id=first_citation["message_id"],
                citation_id=first_citation["id"],
                status="supported",
                note="El fragmento sostiene la afirmación.",
                reviewer_name="Aceptación de prueba",
            )
            session.commit()
            summary["review"] = {
                "citation_id": reviewed.id,
                "status": reviewed.support_review_status,
                "reviewed_by": reviewed.support_reviewed_by,
                "reviewed_at": reviewed.support_reviewed_at,
                "note": reviewed.support_review_note,
            }
        assert summary["review"]["status"] == "supported"

        # Reinicio: nueva conexión y nuevo checkpointer sobre el mismo almacenamiento.
        memory.close()
        engine.dispose()
        engine = create_engine_for_url(settings.database_url)
        factory = create_session_factory(engine)
        memory = open_memory(settings.checkpoints_path)
        with factory() as session:
            view = conversation_view(
                session,
                CaseScope(case_id=case_id),
                reviewer_configured=True,
                factory=factory,
            )
            summary["restart_messages"] = len(view["messages"])
            restored_run = session.get(Run, ctx1.run_id)
            assert restored_run is not None
            assert restored_run.status == "succeeded"
            assert restored_run.trace_status in {"disabled", "submitted", "confirmed", "failed"}
        assert summary["restart_messages"] >= 10

        # Aislamiento: un caso nuevo no ve los hallazgos del caso de demostración.
        with factory() as session:
            other_case_id = create_case(session, "Caso de aceptación aislado")
            session.commit()
        ctx6, result6 = _ask(
            factory,
            settings,
            case_id=other_case_id,
            question=FINDINGS_QUESTION,
            generator=generator,
            embedder=embedder,
            index=index,
            memory=memory,
        )
        assert result6.status == "succeeded"
        facts6 = _turn_facts(factory, ctx6.run_id, FINDINGS_QUESTION)
        assert facts6["tools"] and facts6["tools"][0]["summary"]["total"] == 0
        summary["isolation"] = {"case_id": other_case_id, "total": 0}

        # Reintento: fallo inducido y reintento real sobre la misma pregunta.
        failing = FailingGenerator()
        failed_ctx, failed_result = _ask(
            factory,
            settings,
            case_id=case_id,
            question="¿Qué controles aplican al respaldo?",
            generator=failing,
            embedder=embedder,
            index=index,
            memory=memory,
        )
        assert failed_result.status == "failed"
        retry_ctx = start_retry_turn(
            factory,
            settings,
            scope=CaseScope(case_id=case_id),
            run_id=failed_ctx.run_id,
            generator=generator,
            embedder=embedder,
            index=index,
            token_counter=load_prompt_counter(settings.ollama_model),
        )
        retry_result = execute_turn(retry_ctx, memory=memory)
        assert retry_result.status == "succeeded"
        with factory() as session:
            retry_run = session.get(Run, retry_ctx.run_id)
            assert retry_run.attempt_no == 2
            assert retry_run.retry_of_run_id == failed_ctx.run_id
            assert retry_run.question_message_id == failed_ctx.question_message_id
            summary["retry"] = {
                "failed_run_id": failed_ctx.run_id,
                "retry_run_id": retry_ctx.run_id,
                "attempt_no": retry_run.attempt_no,
                "retry_of_run_id": retry_run.retry_of_run_id,
                "outcome": retry_run.outcome,
            }

        summary["trace"] = {
            "status": facts1["trace_status"],
            "trace_id": facts1["trace_id"],
            "trace_url": facts1["trace_url"],
        }
        summary_path = base / "acceptance-summary.json"
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print("ACEPTACIÓN REAL:", json.dumps(summary, ensure_ascii=False, indent=2))
    finally:
        memory.close()
        embedder.close()
        engine.dispose()
