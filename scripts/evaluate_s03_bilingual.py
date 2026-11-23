"""Evaluador bilingüe de S03, separado de la evaluación histórica."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

VERSION = "005-s03-bilingual-v2"

RISK_CONCEPTS = {
    "prompt_injection": (
        "prompt injection",
        "inyección de prompts",
        "inyeccion de prompts",
        "prompt-injection",
    ),
    "sensitive_information": (
        "sensitive information",
        "información sensible",
        "informacion sensible",
        "divulgación de información",
        "divulgacion de informacion",
    ),
    "supply_chain": ("supply chain", "cadena de suministro"),
    "excessive_agency": ("excessive agency", "agencia excesiva", "exceso de agencia"),
    "insecure_output": (
        "insecure output",
        "manejo inseguro de la salida",
        "salida insegura",
        "output handling",
    ),
    "system_prompt_leak": ("system prompt", "prompt del sistema", "fuga del prompt"),
    "data_poisoning": ("data poisoning", "envenenamiento de datos"),
    "unbounded_consumption": ("unbounded consumption", "consumo ilimitado"),
    "misinformation": ("misinformation", "desinformación", "desinformacion"),
    "vector_embedding": ("embedding", "vector"),
}
RECOMMENDATION_MARKERS = (
    "recomend",
    "recommend",
    "control",
    "mitig",
    "human-in-the-loop",
    "aprobación humana",
    "aprobacion humana",
    "revisión humana",
    "revision humana",
    "validar",
    "restringir",
    "limitar",
    "monitorear",
)


def _normalized(text: str) -> str:
    return (text or "").casefold()


def detect_risks(answer: str) -> list[str]:
    text = _normalized(answer)
    return [
        name
        for name, aliases in RISK_CONCEPTS.items()
        if any(alias.casefold() in text for alias in aliases)
    ]


def has_recommendation(answer: str) -> bool:
    text = _normalized(answer)
    return any(marker.casefold() in text for marker in RECOMMENDATION_MARKERS)


def evaluate_s03(row: dict) -> dict:
    answer = row.get("answer") or ""
    risks = detect_risks(answer)
    recommendation = has_recommendation(answer)
    citations = row.get("citations") or []
    valid_citations = sum(1 for item in citations if item.get("check_status") == "valid")
    if not answer.strip():
        status = "undetermined"
        reason = "sin respuesta conservada"
    elif len(risks) >= 2 and recommendation and valid_citations:
        status = "approved"
        reason = "dos riesgos OWASP y una recomendación, con cita válida"
    else:
        status = "failed"
        missing = []
        if len(risks) < 2:
            missing.append("menos de dos riesgos")
        if not recommendation:
            missing.append("sin recomendación")
        if not valid_citations:
            missing.append("sin cita válida")
        reason = "; ".join(missing)
    return {
        "version": VERSION,
        "old_result": row.get("result"),
        "new_result": status,
        "reason": reason,
        "risks": risks,
        "recommendation": recommendation,
        "citations": len(citations),
        "valid_citations": valid_citations,
        "answer_excerpt": answer[:500],
    }


def _load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def collect(evidence_root: Path) -> list[dict]:
    sources = []
    historical = evidence_root / "005-evaluacion-proveedores"
    for provider in ("ollama", "deepseek", "anthropic"):
        path = historical / f"resultados-{provider}.json"
        for row in _load(path):
            if row.get("scenario") == "S03":
                sources.append(
                    {
                        "sample": "historico-30",
                        "provider": provider,
                        "model": row.get("model"),
                        "run_id": row.get("run_id"),
                        **evaluate_s03(row),
                    }
                )
    focused = evidence_root / "005-estabilizacion" / "reevaluacion-externa-4096"
    for provider in ("deepseek", "anthropic"):
        path = focused / f"resultados-{provider}.json"
        for row in _load(path):
            if row.get("scenario") == "S03":
                sources.append(
                    {
                        "sample": "focalizada-4096",
                        "provider": provider,
                        "model": row.get("model"),
                        "run_id": row.get("run_id"),
                        **evaluate_s03(row),
                    }
                )
    return sources


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    rows = collect(args.evidence_root)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "s03-recalculado.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary = {
        "version": VERSION,
        "criteria": (
            "Dos riesgos OWASP distintos, en español o inglés, una recomendación "
            "de control/mitigación y al menos una cita válida. La respuesta vacía "
            "se deja sin determinar."
        ),
        "rows": len(rows),
        "approved": [row for row in rows if row["new_result"] == "approved"],
        "failed": [row for row in rows if row["new_result"] == "failed"],
        "undetermined": [row for row in rows if row["new_result"] == "undetermined"],
    }
    (args.output_dir / "resumen.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
