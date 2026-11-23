"""Regresiones del evaluador bilingüe S03."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _module():
    spec = importlib.util.spec_from_file_location(
        "evaluate_s03_bilingual", Path("scripts/evaluate_s03_bilingual.py")
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(answer: str) -> dict:
    return {"answer": answer, "citations": [{"check_status": "valid"}]}


def test_english_answer_passes_with_two_risks_and_recommendation() -> None:
    module = _module()
    result = module.evaluate_s03(
        _row(
            "OWASP describes prompt injection and supply chain risks. "
            "Recommendation: validate model output and restrict privileges."
        )
    )

    assert result["new_result"] == "approved"
    assert "prompt_injection" in result["risks"]
    assert "supply_chain" in result["risks"]


def test_spanish_answer_passes_with_two_risks_and_recommendation() -> None:
    module = _module()
    result = module.evaluate_s03(
        _row(
            "OWASP describe inyección de prompts y cadena de suministro. "
            "Se recomienda validar la salida y limitar privilegios."
        )
    )

    assert result["new_result"] == "approved"
    assert "prompt_injection" in result["risks"]
    assert "supply_chain" in result["risks"]


def test_one_risk_is_not_approved() -> None:
    module = _module()
    result = module.evaluate_s03(_row("OWASP describe prompt injection. Se recomienda validar."))

    assert result["new_result"] == "failed"
    assert "menos de dos riesgos" in result["reason"]


def test_empty_answer_is_undetermined_not_approved() -> None:
    module = _module()
    result = module.evaluate_s03({"answer": "", "citations": []})

    assert result["new_result"] == "undetermined"
    assert result["old_result"] is None
