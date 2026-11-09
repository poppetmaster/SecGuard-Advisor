"""Lectura del CSV filtrado de Qualys, sin interpretar contenido de negocio."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass

EXPECTED_COLUMNS: tuple[str, ...] = (
    "IP",
    "Network",
    "DNS",
    "NetBIOS",
    "Tracking Method",
    "OS",
    "IP Status",
    "QID",
    "Title",
    "Vuln Status",
    "Type",
    "Severity",
    "Port",
    "Protocol",
    "FQDN",
    "SSL",
    "First Detected",
    "Last Detected",
    "Times Detected",
    "Date Last Fixed",
    "First Reopened",
    "Last Reopened",
    "Times Reopened",
    "CVE ID",
    "Vendor Reference",
    "Bugtraq ID",
    "Threat",
    "Impact",
    "Solution",
    "Exploitability",
    "Associated Malware",
    "Results",
    "PCI Vuln",
    "Ticket State",
    "Instance",
    "Category",
    "Associated Tags",
    "QDS",
    "ARS",
    "ACS",
    "TruRisk Score",
)


class CsvReadError(ValueError):
    """Error estructural que impide interpretar el CSV."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        detected_columns: tuple[str, ...] = (),
    ) -> None:
        self.code = code
        self.message = message
        self.detected_columns = detected_columns
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class CsvReadResult:
    header: tuple[str, ...]
    rows: tuple[dict[str, str], ...]


def read_csv(
    content: bytes,
    *,
    max_bytes: int,
    max_rows: int,
) -> CsvReadResult:
    """Lee un CSV UTF-8 con BOM, coma y encabezado exacto de 41 columnas."""
    if not content:
        raise CsvReadError("empty_file", "El archivo está vacío.")
    if len(content) > max_bytes:
        raise CsvReadError("file_too_large", "El archivo supera el límite de bytes.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CsvReadError("invalid_encoding", "El archivo no es UTF-8 válido.") from exc
    reader = csv.DictReader(io.StringIO(text, newline=""))
    header = tuple(reader.fieldnames or ())
    if header != EXPECTED_COLUMNS:
        raise CsvReadError(
            "header_mismatch",
            "El encabezado no coincide con las 41 columnas esperadas.",
            detected_columns=header,
        )
    rows: list[dict[str, str]] = []
    for row in reader:
        if len(rows) >= max_rows:
            raise CsvReadError("too_many_rows", "El archivo supera el límite de filas.")
        if any((value or "").strip() for value in row.values()):
            rows.append({key: (value if value is not None else "") for key, value in row.items()})
    if not rows:
        raise CsvReadError("empty_file", "El archivo no contiene registros.")
    return CsvReadResult(header=header, rows=tuple(rows))


def asset_label(row: dict[str, str]) -> str:
    """Etiqueta de presentación: FQDN, DNS, NetBIOS o IP; no es identidad."""
    for column in ("FQDN", "DNS", "NetBIOS", "IP"):
        value = (row.get(column) or "").strip()
        if value:
            return value[:200]
    return "Sin activo"
