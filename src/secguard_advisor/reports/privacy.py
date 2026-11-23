"""Content policy and deterministic asset aliases for the executive report."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_CONTENT_POLICY: dict[str, Any] = {
    "include_aliases": True,
    "allow_ip": False,
    "allow_internal_names": False,
    "include_results": False,
    "include_case_title": False,
    "detail_level": "executive",
}

INDICATOR_LABELS = {
    "positive": "Positivo",
    "negative_no_info": "Negativo / no informado",
    "indeterminate": "Indeterminado",
}
SEVERITY_LABELS = {
    1: "Informativa",
    2: "Baja",
    3: "Media",
    4: "Alta",
    5: "Crítica",
}


@dataclass(frozen=True, slots=True)
class AssetAlias:
    alias: str
    internal_label: str
    critical: int
    high: int
    total: int


def normalize_content_policy(value: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a safe policy; unknown or unsafe values fall back to defaults."""
    policy = dict(DEFAULT_CONTENT_POLICY)
    if not value:
        return policy
    for key in (
        "include_aliases",
        "allow_ip",
        "allow_internal_names",
        "include_results",
        "include_case_title",
    ):
        if isinstance(value.get(key), bool):
            policy[key] = value[key]
    if value.get("detail_level") in {"executive", "technical"}:
        policy["detail_level"] = value["detail_level"]
    return policy


def is_sensitive_field_allowed(policy: dict[str, Any], field: str) -> bool:
    """Whether a sensitive field may be rendered in outbound content."""
    if field in {"ip", "dns", "netbios", "fqdn", "asset_label", "case_title"}:
        return bool(
            policy.get("allow_ip")
            if field in {"ip", "dns", "netbios", "fqdn", "asset_label"}
            else policy.get("include_case_title")
        )
    if field == "results":
        return bool(policy.get("include_results"))
    return True


def alias_assets(items: list[dict[str, Any]]) -> list[AssetAlias]:
    """Assign stable aliases after the deterministic ranking is applied."""
    aliases: list[AssetAlias] = []
    for index, item in enumerate(items, start=1):
        aliases.append(
            AssetAlias(
                alias=f"Activo {index:02d}",
                internal_label=str(item.get("asset_label") or "Sin activo"),
                critical=int(item.get("critical", 0)),
                high=int(item.get("high", 0)),
                total=int(item.get("total", 0)),
            )
        )
    return aliases
