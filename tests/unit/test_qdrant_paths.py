"""Los archivos de control viven fuera del volumen del servidor Qdrant."""

from __future__ import annotations

from pathlib import Path

from secguard_advisor.retrieval import instance, status


def test_control_files_are_separate_from_the_server_volume(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    control = instance.control_dir(storage)

    assert control == storage / "qdrant-control"
    for path in (
        instance.marker_path(storage, "local-dev"),
        instance.lock_path(storage, "local-dev"),
        status.reports_dir(storage, "local-dev"),
    ):
        assert path.is_relative_to(control)
        assert not path.is_relative_to(storage / "qdrant")
