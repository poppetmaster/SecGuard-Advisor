"""Fixtures sintéticos y utilidades para el CSV de Qualys."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

from secguard_advisor.vulnerabilities.adapter import EXPECTED_COLUMNS

EXPLOITABILITY_POSITIVE = (
    "Source: Synthetic\n"
    "Reference: SYN-REF-1\n"
    "Description: Synthetic exploitability block\n"
    "Link: https://example.invalid/exploit"
)
MALWARE_POSITIVE = (
    "Source: Synthetic\n"
    "Malware ID: SYN-MAL-1\n"
    "Type: Synthetic\n"
    "Platform: Test\n"
    "Risk: High\n"
    "Link: https://example.invalid/malware"
)


def make_row(**overrides: str) -> dict[str, str]:
    """Devuelve una fila completa con valores sintéticos y overrides explícitos."""
    row = {
        "IP": "10.0.0.1",
        "Network": "Synthetic",
        "DNS": "asset-1.example",
        "NetBIOS": "ASSET-1",
        "Tracking Method": "Synthetic",
        "OS": "Synthetic OS",
        "IP Status": "Active",
        "QID": "900001",
        "Title": "Synthetic vulnerability",
        "Vuln Status": "Active",
        "Type": "Vulnerability",
        "Severity": "3",
        "Port": "443",
        "Protocol": "tcp",
        "FQDN": "asset-1.example",
        "SSL": "",
        "First Detected": "01/01/2026 00:00:00",
        "Last Detected": "01/02/2026 00:00:00",
        "Times Detected": "1",
        "Date Last Fixed": "",
        "First Reopened": "",
        "Last Reopened": "",
        "Times Reopened": "",
        "CVE ID": "CVE-2026-0001",
        "Vendor Reference": "",
        "Bugtraq ID": "",
        "Threat": "",
        "Impact": "",
        "Solution": "",
        "Exploitability": "",
        "Associated Malware": "",
        "Results": "",
        "PCI Vuln": "",
        "Ticket State": "",
        "Instance": "",
        "Category": "",
        "Associated Tags": "",
        "QDS": "",
        "ARS": "",
        "ACS": "",
        "TruRisk Score": "",
    }
    row.update(overrides)
    return row


def write_csv(
    path: Path,
    rows: list[dict[str, str]],
    *,
    header: tuple[str, ...] = EXPECTED_COLUMNS,
    bom: bool = True,
) -> bytes:
    """Escribe un CSV sintético con coma y BOM opcional."""
    path.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(header), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    content = buffer.getvalue().encode("utf-8-sig" if bom else "utf-8")
    path.write_bytes(content)
    return content


def make_manifest(
    content: bytes,
    rows: list[dict[str, str]],
    *,
    filename: str = "qualys_synthetic_valid.csv",
) -> dict[str, object]:
    """Construye un manifiesto sintético compatible con el insumo."""
    counts: dict[str, int] = {}
    for row in rows:
        status = row.get("Vuln Status", "")
        counts[status] = counts.get(status, 0) + 1
    return {
        "output_filename": filename,
        "output_sha256": hashlib.sha256(content).hexdigest(),
        "output_bytes": len(content),
        "output_detail_rows": len(rows),
        "format": {
            "encoding": "UTF-8 with BOM",
            "delimiter": ",",
            "header_first_record": True,
            "columns": len(EXPECTED_COLUMNS),
            "multiline_fields_preserved": True,
        },
        "output_status_counts": counts,
    }


def write_manifest(path: Path, manifest: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
