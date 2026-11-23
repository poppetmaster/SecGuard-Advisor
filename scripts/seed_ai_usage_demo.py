"""Sembrador ficticio para la evidencia del panel de uso de IA.

No usa datos del usuario ni llama a proveedores. Crea una instancia temporal y
la deja lista para capturas.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from secguard_advisor.ai_usage.evaluation_import import import_evaluation
from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import (
    AiRequest,
    Case,
    Conversation,
    ProviderBudgetLedger,
    Run,
)


def _iso(days_ago: int, hour: int = 15) -> str:
    now = datetime.now(UTC)
    if days_ago == 0:
        return (now - timedelta(hours=2)).replace(microsecond=0).isoformat()
    base = now - timedelta(days=days_ago)
    return base.replace(hour=hour, minute=0, second=0, microsecond=0).isoformat()


def seed(storage: Path) -> None:
    settings = Settings(_env_file=None, storage_dir=storage)
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        case = Case(
            id="case-demo-usage",
            title="Demostración ficticia de uso",
            synthetic_notice="Escenario sintético.",
        )
        session.add(case)
        session.flush()
        session.add(Conversation(id="conv-demo-usage", case_id=case.id, thread_id="demo-usage"))
        session.flush()

        def run(
            run_id: str,
            provider: str,
            model: str,
            *,
            days_ago: int,
            duration: int,
            status: str = "succeeded",
            attempt: int = 1,
            retry_of: str | None = None,
            input_tokens: int | None = 900,
            output_tokens: int | None = 220,
            cost_status: str = "not_applicable",
            cost: Decimal | None = None,
        ) -> None:
            session.add(
                Run(
                    id=run_id,
                    case_id=case.id,
                    conversation_id="conv-demo-usage",
                    status=status,
                    attempt_no=attempt,
                    retry_of_run_id=retry_of,
                    generator_provider=provider,
                    generator_model=model,
                    generator_num_ctx=8192,
                    generator_temperature=0.1,
                    embedding_model="embeddinggemma",
                    embedding_dim=768,
                    prompt_version="chat-v8",
                    duration_ms=duration,
                    usage_input_tokens=input_tokens,
                    usage_output_tokens=output_tokens,
                    usage_source="observed" if input_tokens is not None else None,
                    cost_status=cost_status,
                    cost_usd=cost,
                    cost_tariff_version="2026-11-22" if cost is not None else None,
                    started_at=_iso(days_ago),
                )
            )
            session.flush()

        def request(
            request_id: str,
            run_id: str,
            operation: str,
            provider: str,
            model: str,
            *,
            days_ago: int,
            status: str = "completed",
            input_tokens: int | None = 450,
            output_tokens: int | None = 90,
            cached: int | None = 120,
            cost_status: str = "not_applicable",
            cost: Decimal | None = None,
            usage_source: str = "observed",
            error: str | None = None,
        ) -> None:
            session.add(
                AiRequest(
                    id=request_id,
                    run_id=run_id,
                    operation=operation,
                    attempt_no=1,
                    provider=provider,
                    model=model,
                    started_at=_iso(days_ago),
                    finished_at=_iso(days_ago),
                    status=status,
                    duration_ms=1800 if status == "completed" else 90000,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cached_tokens=cached,
                    usage_source=usage_source,
                    cost_status=cost_status,
                    cost_usd=cost,
                    currency="USD",
                    tariff_version="2026-11-22" if cost is not None else None,
                    error_code=error,
                )
            )
            session.flush()

        run(
            "demo-run-1",
            "deepseek",
            "deepseek-flash",
            days_ago=0,
            duration=4200,
            input_tokens=1200,
            output_tokens=260,
            cost_status="calculated",
            cost=Decimal("0.002411"),
        )
        request(
            "demo-req-1",
            "demo-run-1",
            "decide",
            "deepseek",
            "deepseek-flash",
            days_ago=0,
            input_tokens=300,
            output_tokens=40,
            cached=80,
            cost_status="calculated",
            cost=Decimal("0.000311"),
        )
        request(
            "demo-req-2",
            "demo-run-1",
            "generate",
            "deepseek",
            "deepseek-flash",
            days_ago=0,
            input_tokens=700,
            output_tokens=180,
            cached=120,
            cost_status="calculated",
            cost=Decimal("0.001840"),
        )
        request(
            "demo-req-3",
            "demo-run-1",
            "repair",
            "deepseek",
            "deepseek-flash",
            days_ago=0,
            input_tokens=200,
            output_tokens=40,
            cached=0,
            cost_status="calculated",
            cost=Decimal("0.000260"),
        )
        run(
            "demo-run-2",
            "ollama",
            "qwen3.5:9b",
            days_ago=0,
            duration=31000,
            input_tokens=980,
            output_tokens=240,
        )
        request(
            "demo-req-4",
            "demo-run-2",
            "generate",
            "ollama",
            "qwen3.5:9b",
            days_ago=0,
            input_tokens=980,
            output_tokens=240,
            cached=0,
        )
        run(
            "demo-run-3",
            "anthropic",
            "claude-haiku-5-5",
            days_ago=1,
            duration=8600,
            status="failed",
            input_tokens=None,
            output_tokens=None,
            cost_status="unknown",
        )
        request(
            "demo-req-5",
            "demo-run-3",
            "decide",
            "anthropic",
            "claude-haiku-5-5",
            days_ago=1,
            status="error",
            input_tokens=None,
            output_tokens=None,
            cached=None,
            usage_source="unavailable",
            cost_status="unknown",
            error="invalid_model_output",
        )
        run(
            "demo-run-4",
            "deepseek",
            "deepseek-flash",
            days_ago=3,
            duration=5100,
            attempt=2,
            retry_of="demo-run-1",
            input_tokens=1100,
            output_tokens=210,
            cost_status="calculated",
            cost=Decimal("0.001980"),
        )
        request(
            "demo-req-6",
            "demo-run-4",
            "generate",
            "deepseek",
            "deepseek-flash",
            days_ago=3,
            input_tokens=1100,
            output_tokens=210,
            cached=0,
            cost_status="calculated",
            cost=Decimal("0.001980"),
        )
        run(
            "demo-run-5",
            "ollama",
            "qwen3.5:9b",
            days_ago=5,
            duration=25000,
            input_tokens=800,
            output_tokens=180,
        )
        run(
            "demo-run-6",
            "deepseek",
            "deepseek-flash",
            days_ago=0,
            duration=None,
            status="running",
            input_tokens=240,
            output_tokens=30,
            cost_status="calculated",
            cost=Decimal("0.000120"),
        )
        request(
            "demo-req-7",
            "demo-run-6",
            "decide",
            "deepseek",
            "deepseek-flash",
            days_ago=0,
            input_tokens=240,
            output_tokens=30,
            cached=0,
            cost_status="calculated",
            cost=Decimal("0.000120"),
        )
        session.add(
            ProviderBudgetLedger(
                run_id="demo-run-1",
                attempt_no=1,
                provider="deepseek",
                model="deepseek-flash",
                state="reserved",
                reserved_usd=Decimal("0.500000"),
            )
        )
        session.add(
            ProviderBudgetLedger(
                run_id="demo-run-6",
                attempt_no=1,
                provider="deepseek",
                model="deepseek-flash",
                state="reserved",
                reserved_usd=Decimal("0.400000"),
            )
        )
        session.add(
            ProviderBudgetLedger(
                run_id="demo-run-3",
                attempt_no=1,
                provider="anthropic",
                model="claude-haiku-5-5",
                state="reconciled",
                reserved_usd=Decimal("0.250000"),
                settled_usd=Decimal("0.250000"),
            )
        )
        report = import_evaluation(
            session,
            Path("docs/evidencia/005-evaluacion-proveedores"),
        )
        session.commit()
    engine.dispose()
    print(
        json.dumps(
            {
                "storage": str(storage),
                "evaluation_id": report.evaluation_id,
                "evaluation_results": report.created + report.updated,
            },
            ensure_ascii=False,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--storage", type=Path, required=True)
    args = parser.parse_args()
    seed(args.storage)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
