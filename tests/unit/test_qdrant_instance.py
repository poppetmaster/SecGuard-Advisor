"""Pruebas de identidad de instancia, namespace, marcador y lock."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from secguard_advisor.retrieval import instance


@pytest.fixture()
def storage(tmp_path: Path) -> Path:
    return tmp_path / "storage"


def test_validate_instance_id_accepts_valid_slugs() -> None:
    for value in ("local-dev", "presentacion-2026", "abc", "a" * 40):
        assert instance.validate_instance_id(value) == value


@pytest.mark.parametrize(
    "value",
    (None, "", "ab", "Local-Dev", "-local", "local dev", "local/dev", "a" * 41),
)
def test_validate_instance_id_rejects_invalid_slugs(value: str | None) -> None:
    with pytest.raises(instance.InstanceConfigurationError):
        instance.validate_instance_id(value)


def test_fingerprint_is_stable_when_storage_content_changes(storage: Path) -> None:
    storage.mkdir()
    first = instance.storage_fingerprint(storage, "local-dev")

    (storage / "secguard.sqlite3").write_bytes(b"contenido inicial")
    (storage / "originals").mkdir()
    (storage / "originals" / "doc.txt").write_text("texto", encoding="utf-8")
    second = instance.storage_fingerprint(storage, "local-dev")

    assert first == second


def test_fingerprint_changes_with_storage_path(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()

    assert instance.storage_fingerprint(left, "local-dev") != instance.storage_fingerprint(
        right, "local-dev"
    )


def test_fingerprint_changes_with_instance_id(storage: Path) -> None:
    storage.mkdir()

    assert instance.storage_fingerprint(storage, "local-dev") != instance.storage_fingerprint(
        storage, "presentacion-2026"
    )


def test_instance_prefix_contains_instance_id() -> None:
    assert instance.instance_prefix("local-dev") == "secguard__local-dev__"


def test_ensure_marker_creates_it_on_first_use(storage: Path) -> None:
    marker = instance.ensure_marker(storage, "local-dev", namespace_present=False)

    path = instance.marker_path(storage, "local-dev")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert path.is_file()
    assert marker.instance_id == "local-dev"
    assert payload["instance_id"] == "local-dev"
    assert payload["storage_fingerprint"] == instance.storage_fingerprint(storage, "local-dev")
    assert payload["schema_version"] == instance.MARKER_SCHEMA_VERSION


def test_ensure_marker_refuses_namespace_without_marker(storage: Path) -> None:
    storage.mkdir()

    with pytest.raises(instance.InstanceNamespaceMismatch):
        instance.ensure_marker(storage, "local-dev", namespace_present=True)

    assert not instance.marker_path(storage, "local-dev").exists()


def test_ensure_marker_refuses_instance_id_mismatch(storage: Path) -> None:
    path = instance.marker_path(storage, "local-dev")
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "instance_id": "otra-instancia",
                "storage_fingerprint": instance.storage_fingerprint(storage, "local-dev"),
                "schema_version": instance.MARKER_SCHEMA_VERSION,
                "created_at": "2026-11-22T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(instance.InstanceNamespaceMismatch):
        instance.ensure_marker(storage, "local-dev", namespace_present=False)


def test_ensure_marker_refuses_fingerprint_mismatch(tmp_path: Path) -> None:
    original = tmp_path / "storage"
    original.mkdir()
    instance.ensure_marker(original, "local-dev", namespace_present=False)

    copy = tmp_path / "copy"
    copy.mkdir()
    marker = instance.marker_path(original, "local-dev")
    (copy / "qdrant-control" / "instances").mkdir(parents=True)
    (copy / "qdrant-control" / "instances" / "local-dev.json").write_text(
        marker.read_text(encoding="utf-8"), encoding="utf-8"
    )

    with pytest.raises(instance.InstanceNamespaceMismatch):
        instance.ensure_marker(copy, "local-dev", namespace_present=False)


def test_ensure_marker_accepts_matching_marker(storage: Path) -> None:
    first = instance.ensure_marker(storage, "local-dev", namespace_present=False)
    second = instance.ensure_marker(storage, "local-dev", namespace_present=False)

    assert first == second
    assert instance.read_marker(storage, "local-dev") == first


def test_lock_records_owner_and_releases(storage: Path) -> None:
    with instance.acquire_instance_lock(
        storage, "local-dev", "rebuild", attempt_id="attempt-1"
    ) as owner:
        assert owner.operation == "rebuild"
        assert owner.attempt_id == "attempt-1"
        assert owner.pid == os.getpid()
        payload = json.loads(instance.lock_path(storage, "local-dev").read_text(encoding="utf-8"))
        assert payload["operation"] == "rebuild"
        assert payload["attempt_id"] == "attempt-1"

        observed = instance.inspect_lock(storage, "local-dev")
        assert observed is not None
        assert observed.operation == "rebuild"
        assert observed.attempt_id == "attempt-1"

    assert instance.inspect_lock(storage, "local-dev") is None
    assert instance.lock_path(storage, "local-dev").stat().st_size == 0


def test_lock_rejects_second_acquisition(storage: Path) -> None:
    with (
        instance.acquire_instance_lock(storage, "local-dev", "rebuild"),
        pytest.raises(instance.InstanceLockBusy) as error,
        instance.acquire_instance_lock(storage, "local-dev", "ingestion"),
    ):
        pass

    assert error.value.owner is not None
    assert error.value.owner.operation == "rebuild"


def test_lock_rejects_unknown_operation(storage: Path) -> None:
    with (
        pytest.raises(instance.InstanceConfigurationError),
        instance.acquire_instance_lock(storage, "local-dev", "borrado"),
    ):
        pass


def test_inspect_does_not_create_lock_file(storage: Path) -> None:
    storage.mkdir()

    assert instance.inspect_lock(storage, "local-dev") is None
    assert not instance.lock_path(storage, "local-dev").exists()


def test_inspect_ignores_stale_metadata_when_lock_is_free(storage: Path) -> None:
    path = instance.lock_path(storage, "local-dev")
    path.parent.mkdir(parents=True)
    stale = json.dumps(
        {
            "operation": "rebuild",
            "attempt_id": "viejo",
            "pid": 999_999,
            "started_at": "2026-11-22T00:00:00Z",
        }
    ).encode("utf-8")
    path.write_bytes(stale)

    assert instance.inspect_lock(storage, "local-dev") is None
    assert path.read_bytes() == stale


def test_inspect_does_not_modify_an_existing_lock_file(storage: Path) -> None:
    path = instance.lock_path(storage, "local-dev")
    path.parent.mkdir(parents=True)
    path.write_bytes(b"contenido residual")
    before = (path.read_bytes(), path.stat().st_mtime_ns)

    assert instance.inspect_lock(storage, "local-dev") is None

    assert (path.read_bytes(), path.stat().st_mtime_ns) == before


def test_inspect_reports_unreadable_owner_when_lock_is_held(storage: Path) -> None:
    fcntl = pytest.importorskip("fcntl")
    path = instance.lock_path(storage, "local-dev")
    path.parent.mkdir(parents=True)
    path.write_bytes(b"")
    fd = os.open(path, os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(instance.LockUnreadable):
            instance.inspect_lock(storage, "local-dev")
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
