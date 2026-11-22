"""Reconstrucción del índice Qdrant y consulta de estado (004).

Uso:
    uv run python scripts/rebuild_qdrant.py --status
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from pydantic import ValidationError

from secguard_advisor.config import get_settings
from secguard_advisor.retrieval import instance, status


def _domain(storage_dir: Path, instance_id: str | None) -> tuple[Path, str]:
    settings = get_settings()
    resolved_storage = storage_dir or settings.storage_dir
    resolved_instance = instance_id or settings.instance_id
    return Path(resolved_storage), instance.validate_instance_id(resolved_instance)


def _owner_payload(owner: instance.LockOwner | None) -> dict | None:
    return asdict(owner) if owner is not None else None


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def _error(code: str, message: str) -> int:
    print(f"{code}: {message}", file=sys.stderr)
    _emit(
        {
            "state": None,
            "lock_owner": None,
            "last_terminal": None,
            "error": {"code": code, "message": message},
        }
    )
    return 2


def status_command(storage_dir: Path | None, instance_id: str | None) -> int:
    try:
        resolved_storage, resolved_instance = _domain(storage_dir, instance_id)
    except instance.InstanceConfigurationError, ValidationError:
        return _error(
            "instance_configuration_invalid",
            "SECGUARD_INSTANCE_ID ausente o inválido: se requiere un slug estable "
            "de 3 a 40 caracteres en minúsculas, dígitos o guiones.",
        )
    try:
        result = status.resolve_operation_state(resolved_storage, resolved_instance)
    except instance.InstanceConfigurationError as exc:
        return _error("instance_configuration_invalid", str(exc))
    except instance.LockUnreadable as exc:
        return _error("lock_unreadable", str(exc))
    except status.StatusReportUnreadable as exc:
        return _error("status_report_unreadable", str(exc))

    _emit(
        {
            "state": result.state,
            "lock_owner": _owner_payload(result.lock_owner),
            "last_terminal": result.last_terminal,
            "error": None,
        }
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Reconstruye el índice documental en Qdrant y consulta su estado."
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Consulta de solo lectura del estado de reconstrucción.",
    )
    parser.add_argument("--storage", type=Path, default=None)
    parser.add_argument("--instance", default=None)
    args = parser.parse_args(argv)

    if not args.status:
        parser.error("solo se admite --status en este corte")

    return status_command(args.storage, args.instance)


if __name__ == "__main__":
    raise SystemExit(main())
