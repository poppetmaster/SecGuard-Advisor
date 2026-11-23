"""La migración de telemetría es aditiva y conserva las ejecuciones."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

PREVIOUS_REVISION = "f7a8b9c0d1e2"


def _alembic(storage: Path, revision: str) -> None:
    environment = {
        **os.environ,
        "SECGUARD_STORAGE_DIR": str(storage),
        "SECGUARD_INSTANCE_ID": "migration-usage-test",
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


def test_upgrade_adds_tables_without_rewriting_runs(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    storage.mkdir()
    _alembic(storage, PREVIOUS_REVISION)
    database = storage / "secguard.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            INSERT INTO runs (
                id, case_id, conversation_id, kind, attempt_no, status,
                generator_provider, generator_model, generator_num_ctx,
                generator_temperature, embedding_model, embedding_dim,
                prompt_version, steps_count, tool_calls_count, trace_status, started_at
            ) VALUES (
                'legacy-run', 'legacy-case', 'legacy-conversation', 'chat', 1,
                'succeeded', 'deepseek', 'deepseek-flash', 8192, 0.1,
                'embeddinggemma', 768, 'chat-v8', 0, 0, 'disabled',
                '2026-11-01T00:00:00+00:00'
            )
            """
        )
        connection.execute(
            """
            INSERT INTO ai_provider_profiles (
                provider, model, max_output_tokens, timeout_seconds, updated_at
            ) VALUES
                ('deepseek', 'deepseek-flash', 1200, 90, '2026-11-01T00:00:00+00:00'),
                ('anthropic', 'claude-haiku-5-5', 512, 90, '2026-11-01T00:00:00+00:00'),
                ('ollama', 'qwen3.5:9b', 800, 90, '2026-11-01T00:00:00+00:00')
            """
        )
        connection.commit()

    _alembic(storage, "head")

    with sqlite3.connect(database) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        row = connection.execute(
            "SELECT generator_provider, generator_model, status FROM runs WHERE id='legacy-run'"
        ).fetchone()
        profiles = dict(
            connection.execute(
                "SELECT provider, max_output_tokens FROM ai_provider_profiles"
            ).fetchall()
        )
    assert {"ai_requests", "ai_evaluations", "ai_evaluation_results"} <= tables
    assert row == ("deepseek", "deepseek-flash", "succeeded")
    assert profiles == {"deepseek": 4096, "anthropic": 4096, "ollama": 800}
