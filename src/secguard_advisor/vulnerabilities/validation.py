"""Validación del CSV Qualys, issues, preview y comparación con manifiesto."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from secguard_advisor.config import Settings
from secguard_advisor.vulnerabilities.adapter import CsvReadError, asset_label, read_csv
from secguard_advisor.vulnerabilities.policies import (
    evaluate_exploitability,
    evaluate_malware,
    map_severity,
    normalize_status,
    priority_for,
)

REQUIRED_COLUMNS = (
    "IP",
    "QID",
    "Title",
    "Vuln Status",
    "Severity",
    "First Detected",
    "Last Detected",
)
DATE_PATTERN = re.compile(r"^\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}$")
CVE_PATTERN = re.compile(r"^CVE-\d{4}-\d{4,7}$")
REQUIRED_DATE_COLUMNS = ("First Detected", "Last Detected")
OPTIONAL_DATE_COLUMNS = ("Date Last Fixed", "First Reopened", "Last Reopened")


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    message: str
    severity: str
    row_number: int | None = None
    field: str | None = None


@dataclass(frozen=True, slots=True)
class ManifestComparison:
    status: str
    manifest_sha256: str | None = None
    error_code: str | None = None
    message: str | None = None


@dataclass(frozen=True, slots=True)
class Manifest:
    manifest_sha256: str
    output_sha256: str
    output_bytes: int
    output_rows: int
    columns: int
    status_counts: dict[str, int]


@dataclass(frozen=True, slots=True)
class ValidatedRow:
    row_number: int
    raw_json: str
    asset_label: str
    ip: str | None
    dns: str | None
    netbios: str | None
    fqdn: str | None
    qid: str
    title: str
    vuln_type: str | None
    status_raw: str
    status_normalized: str
    status_group: str
    severity_raw: str
    severity_level: int
    severity_label: str
    port: int | None
    protocol: str | None
    first_detected: str | None
    last_detected: str | None
    first_detected_normalized: str | None
    last_detected_normalized: str | None
    date_last_fixed: str | None
    first_reopened: str | None
    last_reopened: str | None
    times_detected: int | None
    times_reopened: int | None
    exploitability_raw: str | None
    exploitability_eval: str
    exploitability_reason: str | None
    malware_raw: str | None
    malware_eval: str
    malware_reason: str | None
    priority_flag: bool
    priority_reason: str | None
    vendor_metrics_json: str | None
    cves: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ValidationResult:
    status: str
    rows: tuple[ValidatedRow, ...]
    issues: tuple[ValidationIssue, ...]
    error_code: str | None
    error_message: str | None
    row_count: int
    valid_rows: int
    invalid_rows: int
    warning_rows: int
    manual_review_rows: int
    status_counts: dict[str, int]
    severity_counts: dict[str, int]
    exploitability_counts: dict[str, int]
    malware_counts: dict[str, int]
    priority_counts: dict[str, int]
    possible_repeat_groups: int
    possible_repeat_rows: int
    manifest: ManifestComparison
    detected_columns: tuple[str, ...] = ()
    summary: dict[str, object] = field(default_factory=dict)


class ManifestError(ValueError):
    """Manifiesto ausente, ilegible o con estructura inválida."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def load_manifest(path: Path) -> Manifest:
    """Carga un manifiesto local y valida sus campos mínimos."""
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise ManifestError("manifest_invalid", "No se pudo leer el manifiesto.") from exc
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestError("manifest_invalid", "El manifiesto no es JSON válido.") from exc
    if not isinstance(payload, dict):
        raise ManifestError("manifest_invalid", "El manifiesto no es un objeto.")
    try:
        output_sha256 = str(payload["output_sha256"])
        output_bytes = int(payload["output_bytes"])
        output_rows = int(payload["output_detail_rows"])
        columns = int(payload["format"]["columns"])
        raw_counts = payload["output_status_counts"]
        if not isinstance(raw_counts, dict):
            raise TypeError
        status_counts = {str(key): int(value) for key, value in raw_counts.items()}
    except (KeyError, TypeError, ValueError) as exc:
        raise ManifestError("manifest_invalid", "Faltan campos o tienen tipo inválido.") from exc
    if (
        output_bytes < 0
        or output_rows < 0
        or columns < 1
        or any(value < 0 for value in status_counts.values())
    ):
        raise ManifestError("manifest_invalid", "El manifiesto contiene cantidades inválidas.")
    return Manifest(
        manifest_sha256=hashlib.sha256(content).hexdigest(),
        output_sha256=output_sha256,
        output_bytes=output_bytes,
        output_rows=output_rows,
        columns=columns,
        status_counts=status_counts,
    )


def compare_manifest(
    manifest: Manifest,
    *,
    actual_sha256: str,
    actual_bytes: int,
    actual_rows: int,
    actual_columns: int,
    actual_status_counts: dict[str, int],
) -> ManifestComparison:
    """Compara el insumo contra el manifiesto sin exponer valores de filas."""
    keys = set(manifest.status_counts) | set(actual_status_counts)
    counts_match = all(
        manifest.status_counts.get(key, 0) == actual_status_counts.get(key, 0) for key in keys
    )
    if (
        manifest.output_sha256 == actual_sha256
        and manifest.output_bytes == actual_bytes
        and manifest.output_rows == actual_rows
        and manifest.columns == actual_columns
        and counts_match
    ):
        return ManifestComparison("matched", manifest.manifest_sha256)
    return ManifestComparison(
        "mismatch",
        manifest.manifest_sha256,
        "manifest_mismatch",
        "El archivo no coincide con el manifiesto de referencia.",
    )


def _issue(
    code: str,
    message: str,
    severity: str,
    *,
    row_number: int | None = None,
    column: str | None = None,
) -> ValidationIssue:
    return ValidationIssue(
        code=code,
        message=message,
        severity=severity,
        row_number=row_number,
        field=column,
    )


def _optional_text(row: dict[str, str], column: str) -> str | None:
    value = (row.get(column) or "").strip()
    return value or None


def _parse_int(value: str, *, code: str) -> int | None:
    text = value.strip()
    if not text:
        return None
    if not text.isdigit():
        raise ValueError(code)
    return int(text)


def _date_value(value: str, *, required: bool, code: str) -> str | None:
    text = value.strip()
    if not text:
        if required:
            raise ValueError(code)
        return None
    if not DATE_PATTERN.fullmatch(text):
        raise ValueError(code)
    return text


def _validate_row(
    row: dict[str, str],
    row_number: int,
    *,
    settings: Settings,
) -> tuple[ValidatedRow | None, list[ValidationIssue], dict[str, object]]:
    issues: list[ValidationIssue] = []
    for column, value in row.items():
        if len(value) > settings.qualys_max_field_chars:
            issues.append(
                _issue(
                    "field_too_long",
                    "Un campo supera el límite de caracteres.",
                    "error",
                    row_number=row_number,
                    column=column,
                )
            )
    for column in REQUIRED_COLUMNS:
        if not (row.get(column) or "").strip():
            issues.append(
                _issue(
                    "required_field",
                    "Falta un campo obligatorio.",
                    "error",
                    row_number=row_number,
                    column=column,
                )
            )
    qid = (row.get("QID") or "").strip()
    if qid and (not qid.isdigit() or len(qid) > 10):
        issues.append(
            _issue(
                "invalid_qid",
                "El QID no es numérico válido.",
                "error",
                row_number=row_number,
                column="QID",
            )
        )
    severity = None
    try:
        severity = map_severity(row.get("Severity"))
    except ValueError:
        issues.append(
            _issue(
                "invalid_severity",
                "La severidad no es un entero entre 1 y 5.",
                "error",
                row_number=row_number,
                column="Severity",
            )
        )
    for column in REQUIRED_DATE_COLUMNS:
        try:
            _date_value(row.get(column, ""), required=True, code="invalid_date")
        except ValueError:
            issues.append(
                _issue(
                    "invalid_date",
                    "La fecha no tiene el formato esperado.",
                    "error",
                    row_number=row_number,
                    column=column,
                )
            )
    for column in OPTIONAL_DATE_COLUMNS:
        try:
            _date_value(row.get(column, ""), required=False, code="invalid_date")
        except ValueError:
            issues.append(
                _issue(
                    "invalid_date",
                    "La fecha no tiene el formato esperado.",
                    "error",
                    row_number=row_number,
                    column=column,
                )
            )
    port = None
    try:
        port = _parse_int(row.get("Port", ""), code="invalid_port")
        if port is not None and not (0 <= port <= 65535):
            raise ValueError
    except ValueError:
        issues.append(
            _issue(
                "invalid_port",
                "El puerto no es un entero válido.",
                "error",
                row_number=row_number,
                column="Port",
            )
        )
    times_detected = None
    try:
        times_detected = _parse_int(row.get("Times Detected", ""), code="invalid_times_detected")
    except ValueError:
        issues.append(
            _issue(
                "invalid_times_detected",
                "Times Detected no es un entero válido.",
                "error",
                row_number=row_number,
                column="Times Detected",
            )
        )
    times_reopened = None
    try:
        times_reopened = _parse_int(row.get("Times Reopened", ""), code="invalid_times_reopened")
    except ValueError:
        issues.append(
            _issue(
                "invalid_times_reopened",
                "Times Reopened no es un entero válido.",
                "error",
                row_number=row_number,
                column="Times Reopened",
            )
        )
    cves: list[str] = []
    raw_cves = [item.strip() for item in (row.get("CVE ID") or "").split(",") if item.strip()]
    if len(raw_cves) > settings.qualys_max_cves:
        issues.append(
            _issue(
                "too_many_cves",
                "El registro supera el límite de CVE.",
                "error",
                row_number=row_number,
                column="CVE ID",
            )
        )
    for cve in raw_cves:
        if not CVE_PATTERN.fullmatch(cve):
            issues.append(
                _issue(
                    "invalid_cve",
                    "Un CVE no tiene el formato esperado.",
                    "error",
                    row_number=row_number,
                    column="CVE ID",
                )
            )
        else:
            cves.append(cve)
    status = normalize_status(row.get("Vuln Status"))
    if status.manual_review:
        issues.append(
            _issue(
                "unknown_status",
                "Estado desconocido; requiere revisión manual.",
                "manual_review",
                row_number=row_number,
                column="Vuln Status",
            )
        )
    exploitability = evaluate_exploitability(row.get("Exploitability"))
    malware = evaluate_malware(row.get("Associated Malware"))
    if exploitability.state == "indeterminate":
        issues.append(
            _issue(
                "indicator_indeterminate",
                "Explotabilidad indeterminada; requiere revisión manual.",
                "manual_review",
                row_number=row_number,
                column="Exploitability",
            )
        )
    if malware.state == "indeterminate":
        issues.append(
            _issue(
                "indicator_indeterminate",
                "Malware indeterminado; requiere revisión manual.",
                "manual_review",
                row_number=row_number,
                column="Associated Malware",
            )
        )
    if severity is None or any(issue.severity == "error" for issue in issues):
        return (
            None,
            issues,
            {
                "status": status.raw,
                "severity": severity.level if severity is not None else None,
                "exploitability": exploitability.state,
                "malware": malware.state,
            },
        )
    priority_flag, priority_reason = priority_for(exploitability, malware)
    vendor_metrics = {
        "QDS": row.get("QDS", ""),
        "ARS": row.get("ARS", ""),
        "ACS": row.get("ACS", ""),
        "TruRisk Score": row.get("TruRisk Score", ""),
    }
    validated = ValidatedRow(
        row_number=row_number,
        raw_json=json.dumps(row, ensure_ascii=False, sort_keys=False),
        asset_label=asset_label(row),
        ip=_optional_text(row, "IP"),
        dns=_optional_text(row, "DNS"),
        netbios=_optional_text(row, "NetBIOS"),
        fqdn=_optional_text(row, "FQDN"),
        qid=qid,
        title=(row.get("Title") or "").strip(),
        vuln_type=_optional_text(row, "Type"),
        status_raw=status.raw,
        status_normalized=status.normalized,
        status_group=status.group,
        severity_raw=severity.raw,
        severity_level=severity.level,
        severity_label=severity.label,
        port=port,
        protocol=_optional_text(row, "Protocol"),
        first_detected=_optional_text(row, "First Detected"),
        last_detected=_optional_text(row, "Last Detected"),
        first_detected_normalized=_date_value(
            row.get("First Detected", ""), required=False, code="invalid_date"
        ),
        last_detected_normalized=_date_value(
            row.get("Last Detected", ""), required=False, code="invalid_date"
        ),
        date_last_fixed=_optional_text(row, "Date Last Fixed"),
        first_reopened=_optional_text(row, "First Reopened"),
        last_reopened=_optional_text(row, "Last Reopened"),
        times_detected=times_detected,
        times_reopened=times_reopened,
        exploitability_raw=_optional_text(row, "Exploitability"),
        exploitability_eval=exploitability.state,
        exploitability_reason=exploitability.reason,
        malware_raw=_optional_text(row, "Associated Malware"),
        malware_eval=malware.state,
        malware_reason=malware.reason,
        priority_flag=priority_flag,
        priority_reason=priority_reason,
        vendor_metrics_json=json.dumps(vendor_metrics, ensure_ascii=False),
        cves=tuple(cves),
    )
    return (
        validated,
        issues,
        {
            "status": status.raw,
            "severity": severity.level,
            "exploitability": exploitability.state,
            "malware": malware.state,
        },
    )


def validate_csv(
    content: bytes,
    *,
    settings: Settings,
    manifest_path: Path | None = None,
) -> ValidationResult:
    """Valida el archivo completo y devuelve preview, issues y comparación."""
    actual_sha = hashlib.sha256(content).hexdigest()
    actual_bytes = len(content)
    issues: list[ValidationIssue] = []
    manifest_comparison = ManifestComparison("absent")
    manifest: Manifest | None = None
    if manifest_path is not None:
        try:
            manifest = load_manifest(manifest_path)
        except ManifestError as exc:
            manifest_comparison = ManifestComparison(
                "invalid", getattr(exc, "manifest_sha256", None), exc.code, exc.message
            )
            issues.append(_issue(exc.code, exc.message, "error"))
    try:
        read = read_csv(
            content, max_bytes=settings.qualys_max_bytes, max_rows=settings.qualys_max_rows
        )
    except CsvReadError as exc:
        if manifest is not None:
            comparison = compare_manifest(
                manifest,
                actual_sha256=actual_sha,
                actual_bytes=actual_bytes,
                actual_rows=0,
                actual_columns=len(exc.detected_columns),
                actual_status_counts={},
            )
            manifest_comparison = comparison
            if comparison.error_code:
                issues.append(_issue(comparison.error_code, comparison.message or "", "error"))
        return ValidationResult(
            status="rejected",
            rows=(),
            issues=tuple(issues) or (_issue(exc.code, exc.message, "error"),),
            error_code=issues[0].code if issues else exc.code,
            error_message=issues[0].message if issues else exc.message,
            row_count=0,
            valid_rows=0,
            invalid_rows=0,
            warning_rows=0,
            manual_review_rows=0,
            status_counts={},
            severity_counts={},
            exploitability_counts={},
            malware_counts={},
            priority_counts={"both_positive": 0},
            possible_repeat_groups=0,
            possible_repeat_rows=0,
            manifest=manifest_comparison,
            detected_columns=exc.detected_columns,
            summary={},
        )
    status_counts: dict[str, int] = {}
    severity_counts: dict[str, int] = {}
    exploitability_counts: dict[str, int] = {}
    malware_counts: dict[str, int] = {}
    both_positive = 0
    valid_rows: list[ValidatedRow] = []
    invalid_rows = 0
    warning_rows = 0
    manual_review_rows = 0
    repeat_source: list[dict[str, str]] = []
    for row_number, row in enumerate(read.rows, start=1):
        row_status = normalize_status(row.get("Vuln Status"))
        status_counts[row_status.raw] = status_counts.get(row_status.raw, 0) + 1
        try:
            severity = map_severity(row.get("Severity"))
            key = str(severity.level)
            severity_counts[key] = severity_counts.get(key, 0) + 1
        except ValueError:
            pass
        exp = evaluate_exploitability(row.get("Exploitability"))
        mal = evaluate_malware(row.get("Associated Malware"))
        exploitability_counts[exp.state] = exploitability_counts.get(exp.state, 0) + 1
        malware_counts[mal.state] = malware_counts.get(mal.state, 0) + 1
        if priority_for(exp, mal)[0]:
            both_positive += 1
        validated, row_issues, _ = _validate_row(row, row_number, settings=settings)
        issues.extend(row_issues)
        row_has_error = any(item.severity == "error" for item in row_issues)
        if row_has_error:
            invalid_rows += 1
        else:
            valid_rows.append(validated)  # type: ignore[arg-type]
        if any(item.severity == "warning" for item in row_issues):
            warning_rows += 1
        if any(item.severity == "manual_review" for item in row_issues):
            manual_review_rows += 1
        repeat_source.append(row)
    groups: dict[tuple[str, str, str, str], int] = {}
    for row in repeat_source:
        key = (
            (row.get("QID") or "").strip(),
            (row.get("IP") or "").strip(),
            (row.get("Port") or "").strip(),
            (row.get("Protocol") or "").strip(),
        )
        if not key[0] or not key[1]:
            continue
        groups[key] = groups.get(key, 0) + 1
    repeated = [count for count in groups.values() if count > 1]
    possible_repeat_groups = len(repeated)
    possible_repeat_rows = sum(count - 1 for count in repeated)
    if manifest is not None:
        comparison = compare_manifest(
            manifest,
            actual_sha256=actual_sha,
            actual_bytes=actual_bytes,
            actual_rows=len(read.rows),
            actual_columns=len(read.header),
            actual_status_counts=status_counts,
        )
        manifest_comparison = comparison
        if comparison.error_code:
            issues.append(_issue(comparison.error_code, comparison.message or "", "error"))
    rejected = any(item.severity == "error" for item in issues)
    status = "rejected" if rejected else "staged"
    summary = {
        "row_count": len(read.rows),
        "valid_rows": len(valid_rows),
        "invalid_rows": invalid_rows,
        "warning_rows": warning_rows,
        "manual_review_rows": manual_review_rows,
        "status_counts": status_counts,
        "severity_counts": severity_counts,
        "exploitability_counts": exploitability_counts,
        "malware_counts": malware_counts,
        "priority_counts": {"both_positive": both_positive},
        "possible_repeat_groups": possible_repeat_groups,
        "possible_repeat_rows": possible_repeat_rows,
    }
    first_error = next((item for item in issues if item.severity == "error"), None)
    return ValidationResult(
        status=status,
        rows=tuple(valid_rows) if status == "staged" else (),
        issues=tuple(issues),
        error_code=first_error.code if first_error else None,
        error_message=first_error.message if first_error else None,
        row_count=len(read.rows),
        valid_rows=len(valid_rows),
        invalid_rows=invalid_rows,
        warning_rows=warning_rows,
        manual_review_rows=manual_review_rows,
        status_counts=status_counts,
        severity_counts=severity_counts,
        exploitability_counts=exploitability_counts,
        malware_counts=malware_counts,
        priority_counts={"both_positive": both_positive},
        possible_repeat_groups=possible_repeat_groups,
        possible_repeat_rows=possible_repeat_rows,
        manifest=manifest_comparison,
        detected_columns=read.header,
        summary=summary,
    )
