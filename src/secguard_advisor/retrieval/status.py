"""Resolvedor único del estado de reconstrucción.

Lee el lock real y el reporte terminal; no crea, modifica ni repara archivos.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from secguard_advisor.retrieval import instance


class StatusReportUnreadable(instance.InstanceError):
    """El reporte terminal existe pero no puede interpretarse."""

    code = "status_report_unreadable"


@dataclass(frozen=True, slots=True)
class OperationStatus:
    state: str | None
    lock_owner: instance.LockOwner | None = None
    last_terminal: dict | None = None
    error: dict | None = None


def reports_dir(storage_dir: Path, instance_id: str) -> Path:
    return (
        instance.control_dir(storage_dir) / "reports" / instance.validate_instance_id(instance_id)
    )


def _read_terminal(storage_dir: Path, instance_id: str) -> dict | None:
    path = reports_dir(storage_dir, instance_id) / "latest.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        status = payload["status"]
        if status not in {"completed", "partial", "failed"}:
            raise ValueError("estado terminal inválido")
        return {
            "status": status,
            "finished_at": payload.get("finished_at"),
            "report": path.name,
        }
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise StatusReportUnreadable(
            "El reporte terminal de reconstrucción no puede interpretarse."
        ) from exc


def resolve_operation_state(
    storage_dir: Path,
    instance_id: str | None,
) -> OperationStatus:
    """Devuelve el estado observado sin escribir nada."""
    instance_id = instance.validate_instance_id(instance_id)
    owner = instance.inspect_lock(storage_dir, instance_id)
    terminal = _read_terminal(storage_dir, instance_id)

    if owner is not None:
        state = "ingestion_in_progress" if owner.operation == "ingestion" else "rebuild_in_progress"
        return OperationStatus(state=state, lock_owner=owner, last_terminal=terminal)

    if terminal is not None:
        return OperationStatus(state=terminal["status"], last_terminal=terminal)

    return OperationStatus(state="not_started")


def terminal_status(scope_statuses: list[str]) -> str:
    """Estado global a partir de los estados por alcance."""
    if not scope_statuses:
        return "completed"
    if all(item == "completed" for item in scope_statuses):
        return "completed"
    if all(item == "failed" for item in scope_statuses):
        return "failed"
    return "partial"
