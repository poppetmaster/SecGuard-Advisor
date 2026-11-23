"""Deterministic asset aliases and declared top-N trimming."""

from __future__ import annotations

from typing import Any


def apply_asset_aliases(assets_top: dict[str, Any]) -> dict[str, Any]:
    """Return the asset block with stable aliases and an explicit remainder group."""
    items = []
    for index, item in enumerate(assets_top.get("items", []), start=1):
        items.append(
            {
                "alias": f"Activo {index:02d}",
                "internal_label": item.get("asset_label", "Sin activo"),
                "critical": int(item.get("critical", 0)),
                "high": int(item.get("high", 0)),
                "total": int(item.get("total", 0)),
            }
        )
    result = dict(assets_top)
    result["items"] = items
    return result
