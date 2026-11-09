"""Políticas versionadas de severidad, estado e indicadores Qualys."""

from __future__ import annotations

import re
from dataclasses import dataclass

from secguard_advisor.vulnerabilities import (
    PRIORITY_RULE_VERSION,
    SEVERITY_POLICY_VERSION,
    STATUS_POLICY_VERSION,
)

SEVERITY_LABELS: dict[int, str] = {
    1: "Informativa",
    2: "Baja",
    3: "Media",
    4: "Alta",
    5: "Crítica",
}
STATUS_VALUES: dict[str, tuple[str, str]] = {
    "Active": ("active", "pending_known"),
    "New": ("new", "pending_known"),
    "Re-Opened": ("reopened", "pending_known"),
    "Fixed": ("fixed", "fixed"),
}
MANUAL_REVIEW = ("manual_review", "manual_review")
INDICATOR_STATES = ("positive", "negative_no_info", "indeterminate")
NEGATIVE_MARKERS = frozenset(
    {
        "n/a",
        "na",
        "none",
        "no",
        "no conocido",
        "no conocida",
        "no detectado",
        "no detectada",
        "not known",
        "not detected",
    }
)
_LABEL_RE = re.compile(r"^\s*([A-Za-z][A-Za-z ]{1,30}):\s*(.*)$")


@dataclass(frozen=True, slots=True)
class SeverityResult:
    raw: str
    level: int
    label: str
    policy_version: str = SEVERITY_POLICY_VERSION


@dataclass(frozen=True, slots=True)
class StatusResult:
    raw: str
    normalized: str
    group: str
    manual_review: bool
    policy_version: str = STATUS_POLICY_VERSION


@dataclass(frozen=True, slots=True)
class IndicatorEvaluation:
    state: str
    reason: str
    rule_version: str = PRIORITY_RULE_VERSION

    @property
    def positive(self) -> bool:
        return self.state == "positive"


def map_severity(raw: str | None) -> SeverityResult:
    """Convierte ``Severity`` 1-5 a la escala de presentación del proyecto."""
    value = (raw or "").strip()
    if not value.isdigit():
        raise ValueError("severity_not_integer")
    level = int(value)
    if level not in SEVERITY_LABELS:
        raise ValueError("severity_out_of_range")
    return SeverityResult(raw=value, level=level, label=SEVERITY_LABELS[level])


def normalize_status(raw: str | None) -> StatusResult:
    """Normaliza los cuatro estados admitidos; el resto queda en revisión manual."""
    value = (raw or "").strip()
    normalized, group = STATUS_VALUES.get(value, MANUAL_REVIEW)
    return StatusResult(
        raw=value,
        normalized=normalized,
        group=group,
        manual_review=normalized == "manual_review",
    )


def _is_negative(value: str) -> bool:
    cleaned = " ".join(value.strip().lower().rstrip(".").split())
    return cleaned in NEGATIVE_MARKERS


def _has_positive_marker(value: str) -> bool:
    return bool(value.strip()) and not _is_negative(value)


def _parse_blocks(raw: str | None) -> list[dict[str, str]]:
    text = (raw or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []
    blocks: list[dict[str, str]] = []
    for chunk in re.split(r"\n\s*\n", text):
        fields: dict[str, str] = {}
        current: str | None = None
        for line in chunk.splitlines():
            match = _LABEL_RE.match(line)
            if match:
                current = match.group(1).strip()
                fields[current] = match.group(2).strip()
            elif current is not None:
                fields[current] = f"{fields[current]}\n{line.strip()}".strip()
        if fields:
            blocks.append(fields)
    return blocks


def evaluate_exploitability(raw: str | None) -> IndicatorEvaluation:
    """Evalúa ``Exploitability`` por bloques estructurados."""
    if not (raw or "").strip():
        return IndicatorEvaluation("indeterminate", "Campo vacío")
    if _is_negative(raw or ""):
        return IndicatorEvaluation("negative_no_info", "Solo marcadores negativos")
    blocks = _parse_blocks(raw)
    if not blocks:
        return IndicatorEvaluation("indeterminate", "Estructura no reconocida")
    for block in blocks:
        source = block.get("Source", "")
        references = (
            block.get("Reference", ""),
            block.get("Link", ""),
            block.get("Description", ""),
        )
        if _has_positive_marker(source) and any(_has_positive_marker(item) for item in references):
            return IndicatorEvaluation(
                "positive", "Bloque con Source y Reference, Link o Description"
            )
    if all(_is_negative(value) for block in blocks for value in block.values() if value.strip()):
        return IndicatorEvaluation("negative_no_info", "Solo marcadores negativos")
    return IndicatorEvaluation("indeterminate", "Estructura no reconocida")


def evaluate_malware(raw: str | None) -> IndicatorEvaluation:
    """Evalúa ``Associated Malware`` por bloques estructurados."""
    if not (raw or "").strip():
        return IndicatorEvaluation("indeterminate", "Campo vacío")
    if _is_negative(raw or ""):
        return IndicatorEvaluation("negative_no_info", "Solo marcadores negativos")
    blocks = _parse_blocks(raw)
    if not blocks:
        return IndicatorEvaluation("indeterminate", "Estructura no reconocida")
    for block in blocks:
        malware_id = block.get("Malware ID", "")
        evidence = (block.get("Type", ""), block.get("Risk", ""), block.get("Link", ""))
        if _has_positive_marker(malware_id) and any(
            _has_positive_marker(item) for item in evidence
        ):
            return IndicatorEvaluation("positive", "Malware ID con Type, Risk o Link")
    if all(_is_negative(value) for block in blocks for value in block.values() if value.strip()):
        return IndicatorEvaluation("negative_no_info", "Solo marcadores negativos")
    return IndicatorEvaluation("indeterminate", "Estructura no reconocida")


def priority_for(
    exploitability: IndicatorEvaluation,
    malware: IndicatorEvaluation,
) -> tuple[bool, str | None]:
    """Activa la prioridad conjunta solo con ambos indicadores positivos."""
    if exploitability.positive and malware.positive:
        return True, "Explotabilidad positiva y malware positivo"
    return False, None
