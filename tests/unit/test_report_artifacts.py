"""Atomic immutable artifacts."""

from pathlib import Path

import pytest

from secguard_advisor.config import Settings
from secguard_advisor.reports.artifacts import read_artifact, write_artifact


def test_artifact_write_and_duplicate(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, storage_dir=tmp_path / "storage")
    digest, size = write_artifact(settings, "case/report/v1/file.txt", b"hola")
    assert size == 4
    assert len(digest) == 64
    assert read_artifact(settings, "case/report/v1/file.txt") == b"hola"
    with pytest.raises(FileExistsError):
        write_artifact(settings, "case/report/v1/file.txt", b"otra")
