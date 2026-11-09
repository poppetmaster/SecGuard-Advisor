"""Importación y consulta de vulnerabilidades Qualys."""

from __future__ import annotations

ADAPTER_VERSION = "qualys-csv-1"
SEVERITY_POLICY_VERSION = "project-severity-1-5-v1"
STATUS_POLICY_VERSION = "qualys-status-v1"
PRIORITY_RULE_VERSION = "qualys-evidence-both-v1"

__all__ = [
    "ADAPTER_VERSION",
    "PRIORITY_RULE_VERSION",
    "SEVERITY_POLICY_VERSION",
    "STATUS_POLICY_VERSION",
]
