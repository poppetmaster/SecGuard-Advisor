"""Evaluación funcional con el umbral calibrado y congelado."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from secguard_advisor.config import Settings

pytestmark = pytest.mark.integration
THRESHOLD = 0.5033


def test_final_evaluation_passes_every_criterion(tmp_path: Path) -> None:
    # El conftest fija RETRIEVAL_MIN_SCORE=0.0 para pruebas; se lee el valor
    # configurado del modelo, que es el umbral calibrado y congelado.
    configured = Settings.model_fields["retrieval_min_score"].default
    assert configured == THRESHOLD
    output = tmp_path / "evaluation.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/qdrant_threshold.py",
            "--mode",
            "evaluate",
            "--dataset",
            "final",
            "--backend",
            "server",
            "--instance",
            "cut6-test-final",
            "--threshold",
            str(configured),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["modality"] == "server"
    assert report["qdrant_version"]
    assert report["threshold"] == configured
    assert report["dataset_sha256"]
    assert report["outcome"]["passed"] is True
    criteria = {item["name"]: item for item in report["outcome"]["criteria"]}
    assert all(item["passed"] for item in criteria.values()), criteria
    assert report["metrics"]["retrieval_ok"] == report["metrics"]["retrieval_total"]
    assert report["metrics"]["non_relevant_accepted"] == 0
    assert report["isolation"]["violations"] == 0
    assert report["versions"]["current_only"] is True
    assert report["versions"]["superseded_leaked"] is False
    assert report["versions"]["historical_citation"] == "valid"
    assert report["qualys"]["unchanged"] is True
