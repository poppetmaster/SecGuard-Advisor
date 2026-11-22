"""Lock de instancia entre procesos reales: rechazo, liberación y SIGKILL."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
from qdrant_client import QdrantClient

from secguard_advisor.retrieval import instance
from secguard_advisor.retrieval.collections import public_scope
from secguard_advisor.retrieval.index import IndexedChunk, QdrantIndex

INSTANCE = "test-local"
HOLDER = r"""
import sys, time
from pathlib import Path
from secguard_advisor.retrieval import instance

storage, instance_id, operation, ready, stop = sys.argv[1:6]
ready_path = Path(ready)
stop_path = Path(stop)
with instance.acquire_instance_lock(
    Path(storage), instance_id, operation, attempt_id="proc-holder"
):
    ready_path.write_text("ready", encoding="utf-8")
    deadline = time.monotonic() + 30
    while not stop_path.exists():
        if time.monotonic() > deadline:
            break
        time.sleep(0.02)
"""
CONTENDER = r"""
import sys
from pathlib import Path
from secguard_advisor.retrieval import instance

storage, instance_id, result = sys.argv[1:4]
try:
    with instance.acquire_instance_lock(Path(storage), instance_id, "rebuild"):
        Path(result).write_text("acquired", encoding="utf-8")
except instance.InstanceLockBusy as exc:
    Path(result).write_text(instance.lock_conflict_code(exc.owner), encoding="utf-8")
"""


def _wait_for(path: Path, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            return
        time.sleep(0.02)
    raise AssertionError(f"No apareció {path} en {timeout}s")


def _holder(storage: Path, operation: str, ready: Path, stop: Path):
    return subprocess.Popen(
        [
            sys.executable,
            "-c",
            HOLDER,
            str(storage),
            INSTANCE,
            operation,
            str(ready),
            str(stop),
        ],
        cwd=Path(__file__).resolve().parents[2],
    )


def _chunk() -> IndexedChunk:
    return IndexedChunk(
        chunk_id="a" * 32,
        text="texto",
        embedding=[1.0, 0.0, 0.0, 0.0],
        document_id="d" * 32,
        version_id="v" * 32,
        origin="public_corpus",
        source_id="sample",
        page=1,
        section=None,
        locator="p. 1",
    )


def test_ingestion_and_rebuild_are_mutually_excluded(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    storage.mkdir()
    ready = tmp_path / "ready"
    stop = tmp_path / "stop"
    holder = _holder(storage, "ingestion", ready, stop)
    try:
        _wait_for(ready)

        result = tmp_path / "contender"
        contender = subprocess.run(
            [
                sys.executable,
                "-c",
                CONTENDER,
                str(storage),
                INSTANCE,
                str(result),
            ],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True,
            text=True,
            timeout=20,
        )

        assert contender.returncode == 0
        assert result.read_text(encoding="utf-8") == "ingestion_in_progress"
        with (
            pytest.raises(instance.InstanceLockBusy) as error,
            instance.acquire_instance_lock(storage, INSTANCE, "rebuild"),
        ):
            pass
        assert error.value.owner is not None
        assert error.value.owner.operation == "ingestion"
    finally:
        stop.write_text("stop", encoding="utf-8")
        holder.wait(timeout=10)

    assert holder.returncode == 0
    assert instance.inspect_lock(storage, INSTANCE) is None
    with instance.acquire_instance_lock(storage, INSTANCE, "rebuild") as owner:
        assert owner.operation == "rebuild"


def test_sigkill_releases_the_lock_and_keeps_the_alias(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    storage.mkdir()
    client = QdrantClient(path=str(tmp_path / "qdrant"))
    index = QdrantIndex(
        url="http://127.0.0.1:6333",
        instance_id=INSTANCE,
        client=client,
        storage_dir=storage,
    )
    index.upsert(public_scope(), "fake-embedding", 4, [_chunk()])
    collection = index.active_collection(public_scope(), "fake-embedding", 4)
    assert collection is not None

    ready = tmp_path / "ready"
    stop = tmp_path / "stop"
    holder = _holder(storage, "rebuild", ready, stop)
    try:
        _wait_for(ready)
        os.kill(holder.pid, signal.SIGKILL)
        holder.wait(timeout=10)
    finally:
        if holder.poll() is None:
            holder.kill()
            holder.wait(timeout=10)

    lock_file = instance.lock_path(storage, INSTANCE)
    assert lock_file.read_text(encoding="utf-8").strip()
    assert instance.inspect_lock(storage, INSTANCE) is None
    assert index.active_collection(public_scope(), "fake-embedding", 4) == collection
    hits = index.query(public_scope(), "fake-embedding", 4, [1.0, 0.0, 0.0, 0.0])
    assert {hit.chunk_id for hit in hits} == {"a" * 32}
    with instance.acquire_instance_lock(storage, INSTANCE, "ingestion") as owner:
        assert owner.operation == "ingestion"
    index.close()
