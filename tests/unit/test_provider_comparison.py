"""Conjunto congelado y ejecutor de comparación (Entrega 3)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from tests.fixtures.provider_comparison import QUESTIONS, dataset_sha256

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "compare_providers", ROOT / "scripts" / "compare_providers.py"
)
assert SPEC and SPEC.loader
compare = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compare)


def test_dataset_is_frozen_with_ten_questions() -> None:
    assert len(QUESTIONS) == 10
    assert sum(1 for item in QUESTIONS if item["must_cite"]) == 8
    assert sum(1 for item in QUESTIONS if item["expect_abstention"]) == 2
    assert dataset_sha256() == "92778d5cdffca49c065354a4c5e816d8af678c30ae795d5fd506ffe8db5c5129"


def test_summary_separates_automatic_metrics_and_semantics() -> None:
    results = [
        {
            "must_cite": True,
            "expect_abstention": False,
            "outcome": "answered",
            "duration_ms": 100,
            "citations": [{"document_title": "A"}],
            "citation_hit": True,
            "cost": {"status": "calculated", "usd": "0.0001"},
        },
        {
            "must_cite": True,
            "expect_abstention": False,
            "outcome": "insufficient_evidence",
            "duration_ms": 200,
            "citations": [],
            "citation_hit": False,
            "cost": {"status": "unknown", "usd": None},
        },
        {
            "must_cite": False,
            "expect_abstention": True,
            "outcome": "insufficient_evidence",
            "duration_ms": 300,
            "citations": [],
            "citation_hit": False,
            "cost": {"status": "calculated", "usd": "0.0002"},
        },
    ]

    summary = compare._summarize(results)

    assert summary["turns"] == 3
    assert summary["answered"] == 1
    assert summary["expected_citations_hit"] == 1
    assert summary["abstentions_observed"] == 1
    assert summary["cost_unknown_turns"] == 1
    assert summary["semantic_evaluation"] == "not_performed"


def test_deepseek_mock_comparison_is_labeled_simulated(tmp_path: Path) -> None:
    report = compare.run("deepseek", "mock", tmp_path / "deepseek")

    assert report["provider"] == "deepseek"
    assert report["transport"] == "mock"
    assert report["retrieval"] == "fake-embeddings"
    assert report["dataset"]["questions"] == 10
    assert len(report["results"]) == 10
    assert report["metrics"]["semantic_evaluation"] == "not_performed"
    assert report["results"][0]["cost"]["status"] == "calculated"


def test_anthropic_mock_comparison_is_labeled_simulated(tmp_path: Path) -> None:
    report = compare.run("anthropic", "mock", tmp_path / "anthropic")

    assert report["provider"] == "anthropic"
    assert report["transport"] == "mock"
    assert len(report["results"]) == 10
    assert report["metrics"]["semantic_evaluation"] == "not_performed"
