"""Atomic immutable report artifacts."""

from __future__ import annotations

import os
from pathlib import Path

from secguard_advisor.config import Settings
from secguard_advisor.reports.canonical import sha256_hex


def version_directory(settings: Settings, case_id: str, report_id: str, version: int) -> Path:
    return settings.reports_dir / case_id / report_id / f"v{version}"


def relative_artifact_path(case_id: str, report_id: str, version: int, filename: str) -> str:
    return f"{case_id}/{report_id}/v{version}/{filename}"


def write_artifact(settings: Settings, relative_path: str, content: bytes) -> tuple[str, int]:
    """Write content atomically without overwriting an existing artifact."""
    target = settings.reports_dir / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise FileExistsError(f"El artefacto ya existe: {relative_path}")
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    temporary.write_bytes(content)
    os.replace(temporary, target)
    return sha256_hex(content), len(content)


def read_artifact(settings: Settings, relative_path: str) -> bytes:
    return (settings.reports_dir / relative_path).read_bytes()
