"""Content policy and alias defaults."""

from secguard_advisor.reports.privacy import (
    DEFAULT_CONTENT_POLICY,
    alias_assets,
    normalize_content_policy,
)


def test_default_policy_excludes_sensitive_content() -> None:
    policy = normalize_content_policy()
    assert policy == DEFAULT_CONTENT_POLICY
    assert policy["allow_ip"] is False
    assert policy["allow_internal_names"] is False
    assert policy["include_results"] is False
    assert policy["include_case_title"] is False


def test_aliases_are_deterministic_and_ordered() -> None:
    aliases = alias_assets(
        [
            {"asset_label": "host-01", "critical": 2, "high": 1, "total": 3},
            {"asset_label": "host-02", "critical": 0, "high": 1, "total": 1},
        ]
    )
    assert aliases[0].alias == "Activo 01"
    assert aliases[0].internal_label == "host-01"
    assert aliases[1].alias == "Activo 02"
