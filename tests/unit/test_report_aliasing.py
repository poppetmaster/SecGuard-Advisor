"""Asset alias and top-N trimming."""

from secguard_advisor.reports.aliasing import apply_asset_aliases


def test_aliases_preserve_counts_and_rank() -> None:
    block = {
        "top_n": 5,
        "items": [
            {"asset_label": "a", "critical": 3, "high": 0, "total": 3},
            {"asset_label": "b", "critical": 1, "high": 2, "total": 3},
        ],
        "recorted": False,
    }
    result = apply_asset_aliases(block)
    assert [item["alias"] for item in result["items"]] == ["Activo 01", "Activo 02"]
    assert result["items"][1]["internal_label"] == "b"
    assert result["items"][1]["high"] == 2
