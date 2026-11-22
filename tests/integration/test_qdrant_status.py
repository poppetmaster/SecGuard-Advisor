"""Integración de `rebuild_qdrant.py --status` sin efectos de escritura."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from secguard_advisor.retrieval import instance

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "rebuild_qdrant.py"
INSTANCE = "test-local"


def _run(storage: Path, instance_id: str = INSTANCE, env: dict | None = None):
    environment = {
        **os.environ,
        "SECGUARD_STORAGE_DIR": str(storage),
        "SECGUARD_INSTANCE_ID": instance_id,
    }
    if env:
        environment.update(env)
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--status"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )


def _listing(storage: Path) -> set[Path]:
    return {p for p in storage.rglob("*")} if storage.exists() else set()


def test_not_started_without_state_and_without_writes(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    storage.mkdir()
    before = _listing(storage)

    result = _run(storage)

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["state"] == "not_started"
    assert payload["last_terminal"] is None
    assert _listing(storage) == before


def test_terminal_status_is_reported(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    reports = storage / "qdrant-control" / "reports" / INSTANCE
    reports.mkdir(parents=True)
    (reports / "latest.json").write_text(
        json.dumps({"status": "partial", "finished_at": "2026-11-22T10:00:00Z"}),
        encoding="utf-8",
    )

    result = _run(storage)

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["state"] == "partial"
    assert payload["last_terminal"]["status"] == "partial"


def test_unreadable_report_returns_exit_2_without_repair(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    reports = storage / "qdrant-control" / "reports" / INSTANCE
    reports.mkdir(parents=True)
    path = reports / "latest.json"
    path.write_text("{no-json", encoding="utf-8")

    result = _run(storage)

    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload["state"] is None
    assert payload["last_terminal"] is None
    assert payload["error"]["code"] == "status_report_unreadable"
    assert result.stderr.strip()
    assert path.read_text(encoding="utf-8") == "{no-json"


def test_invalid_instance_returns_exit_2_without_creating_files(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    storage.mkdir()
    before = _listing(storage)

    result = _run(storage, instance_id="Bad Id")

    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload["error"]["code"] == "instance_configuration_invalid"
    assert payload["state"] is None
    assert _listing(storage) == before


def test_lock_held_without_owner_is_unreadable(tmp_path: Path) -> None:
    fcntl = pytest.importorskip("fcntl")
    storage = tmp_path / "storage"
    path = instance.lock_path(storage, INSTANCE)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"")
    fd = os.open(path, os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = _run(storage)
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)

    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload["error"]["code"] == "lock_unreadable"
    assert payload["state"] is None
    assert payload["last_terminal"] is None
