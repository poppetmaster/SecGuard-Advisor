"""Pruebas de la migración de proveedor y del registro por ejecución (Entrega 1)."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from sqlalchemy import select
from tests.fixtures.conversation import build_env
from tests.fixtures.fakes import FakeEmbedder, FakeTokenCounter, ScriptedGenerator

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.conversation.turn import start_question_turn
from secguard_advisor.db.models import Run

PREVIOUS_REVISION = "b7f2c9d1e4a6"


def _alembic(storage: Path, revision: str) -> None:
    environment = {
        **os.environ,
        "SECGUARD_STORAGE_DIR": str(storage),
        "SECGUARD_INSTANCE_ID": "migration-test",
        "LANGSMITH_TRACING": "false",
    }
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revision],
        cwd=Path(__file__).resolve().parents[2],
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr


def test_existing_runs_are_backfilled_as_ollama(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    storage.mkdir()
    _alembic(storage, PREVIOUS_REVISION)

    database = storage / "secguard.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            INSERT INTO runs (
                id, case_id, conversation_id, kind, attempt_no, status,
                generator_model, generator_num_ctx, generator_temperature,
                embedding_model, embedding_dim, prompt_version,
                steps_count, tool_calls_count, trace_status, started_at
            ) VALUES (
                'old-run', 'old-case', 'old-conversation', 'chat', 1, 'succeeded',
                'qwen3.5:9b', 8192, 0.1, 'embeddinggemma', 768, 'chat-v8',
                0, 0, 'disabled', '2026-11-01T00:00:00+00:00'
            )
            """
        )
        connection.commit()

    _alembic(storage, "head")

    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT generator_provider, generator_identity, cost_status, cost_usd "
            "FROM runs WHERE id = 'old-run'"
        ).fetchone()

    assert row == ("ollama", None, "not_applicable", None)


class _ProviderGenerator(ScriptedGenerator):
    provider = "ollama"
    identity = "digest-test"

    def __init__(self) -> None:
        super().__init__(payloads=[])


def test_start_question_turn_records_provider_and_identity(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False)
    generator = _ProviderGenerator()

    context = start_question_turn(
        env.factory,
        env.settings,
        scope=CaseScope(case_id=env.case_id),
        question="¿Qué controles aplican?",
        generator=generator,
        embedder=FakeEmbedder(),
        index=env.index,
        token_counter=FakeTokenCounter(),
    )

    with env.factory() as session:
        run = session.scalar(select(Run).where(Run.id == context.run_id))

    assert run is not None
    assert run.generator_provider == "ollama"
    assert run.generator_identity == "digest-test"
    assert run.cost_status == "not_applicable"
    assert run.cost_usd is None
