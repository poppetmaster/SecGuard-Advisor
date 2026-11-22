"""Pruebas del resolvedor único de estado de reconstrucción."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from secguard_advisor.retrieval import instance, status

INSTANCE = "test-local"


def _reports(storage: Path) -> Path:
    return instance.control_dir(storage) / "reports" / INSTANCE


def _write_report(storage: Path, payload: dict) -> Path:
    path = _reports(storage) / "latest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _listing(storage: Path) -> set[Path]:
    if not storage.exists():
        return set()
    return {p for p in storage.rglob("*")}


def test_not_started_without_state_creates_nothing(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    storage.mkdir()
    before = _listing(storage)

    result = status.resolve_operation_state(storage, INSTANCE)

    assert result.state == "not_started"
    assert result.lock_owner is None
    assert result.last_terminal is None
    assert _listing(storage) == before


@pytest.mark.parametrize("terminal", ["completed", "partial", "failed"])
def test_last_terminal_is_reported(tmp_path: Path, terminal: str) -> None:
    storage = tmp_path / "storage"
    storage.mkdir()
    _write_report(storage, {"status": terminal, "finished_at": "2026-11-22T10:00:00Z"})

    result = status.resolve_operation_state(storage, INSTANCE)

    assert result.state == terminal
    assert result.last_terminal == {
        "status": terminal,
        "finished_at": "2026-11-22T10:00:00Z",
        "report": "latest.json",
    }


def test_active_ingestion_is_not_reported_as_rebuild(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    storage.mkdir()

    with instance.acquire_instance_lock(storage, INSTANCE, "ingestion", attempt_id="ing-1"):
        result = status.resolve_operation_state(storage, INSTANCE)

    assert result.state == "ingestion_in_progress"
    assert result.lock_owner is not None
    assert result.lock_owner.operation == "ingestion"


def test_active_rebuild_is_reported(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    storage.mkdir()

    with instance.acquire_instance_lock(storage, INSTANCE, "rebuild", attempt_id="reb-1"):
        result = status.resolve_operation_state(storage, INSTANCE)

    assert result.state == "rebuild_in_progress"
    assert result.lock_owner is not None
    assert result.lock_owner.attempt_id == "reb-1"


def test_stale_metadata_with_free_lock_is_ignored(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    storage.mkdir()
    lock = instance.lock_path(storage, INSTANCE)
    lock.parent.mkdir(parents=True)
    lock.write_text(
        json.dumps(
            {
                "operation": "rebuild",
                "attempt_id": "viejo",
                "pid": 999999,
                "started_at": "2026-11-22T09:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    result = status.resolve_operation_state(storage, INSTANCE)

    assert result.state == "not_started"
    assert result.lock_owner is None
    assert lock.read_text(encoding="utf-8")


def test_unreadable_report_raises_without_modifying_it(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    storage.mkdir()
    path = _reports(storage) / "latest.json"
    path.parent.mkdir(parents=True)
    path.write_text("{no-json", encoding="utf-8")
    before = path.read_bytes()

    with pytest.raises(status.StatusReportUnreadable):
        status.resolve_operation_state(storage, INSTANCE)

    assert path.read_bytes() == before


def test_invalid_instance_id_raises_configuration_error(tmp_path: Path) -> None:
    with pytest.raises(instance.InstanceConfigurationError):
        status.resolve_operation_state(tmp_path, "Bad Id")


def test_terminal_status_mapping() -> None:
    assert status.terminal_status(["completed", "completed"]) == "completed"
    assert status.terminal_status(["completed", "failed"]) == "partial"
    assert status.terminal_status(["partial"]) == "partial"
    assert status.terminal_status(["failed", "failed"]) == "failed"
    assert status.terminal_status([]) == "completed"
