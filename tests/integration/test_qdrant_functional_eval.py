"""Evaluación funcional con el umbral calibrado y congelado."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from secguard_advisor.config import Settings

pytestmark = pytest.mark.integration


def test_evaluation_uses_the_frozen_threshold(tmp_path: Path) -> None:
    threshold = Settings(_env_file=None).retrieval_min_score
    output = tmp_path / "evaluation.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/qdrant_threshold.py",
            "--mode",
            "evaluate",
            "--threshold",
            str(threshold),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["threshold_applied"] == threshold
    assert report["metrics"]["retrieval_total"] > 0
    assert report["isolation"]["crossed"] is False
    assert report["versions"]["historical_citation"] == "valid"
