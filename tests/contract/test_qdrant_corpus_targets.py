"""Contrato de los targets de corpus/demo sobre Qdrant."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_corpus_scripts_use_qdrant_and_not_chroma() -> None:
    for name in ("ingest_corpus.py", "prepare_demo.py"):
        content = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        assert "QdrantIndex" in content
        assert "ingest_public_corpus_locked" in content
        assert "ChromaIndex" not in content
        assert "chroma_dir" not in content


def test_targets_are_listed_and_do_not_invoke_chroma() -> None:
    help_output = subprocess.run(
        ["make", "-s", "help"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout
    for target in ("corpus-ingest", "demo-prepare"):
        assert target in help_output

    dry_run = subprocess.run(
        ["make", "-n", "corpus-ingest", "demo-prepare"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.lower()
    assert "chroma" not in dry_run
