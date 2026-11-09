"""Pruebas de políticas de severidad, estado e indicadores Qualys."""

import pytest

from secguard_advisor.vulnerabilities import (
    PRIORITY_RULE_VERSION,
    SEVERITY_POLICY_VERSION,
    STATUS_POLICY_VERSION,
)
from secguard_advisor.vulnerabilities.policies import (
    evaluate_exploitability,
    evaluate_malware,
    map_severity,
    normalize_status,
    priority_for,
)


def test_severity_uses_project_one_to_five_labels() -> None:
    assert [map_severity(str(level)).label for level in range(1, 6)] == [
        "Informativa",
        "Baja",
        "Media",
        "Alta",
        "Crítica",
    ]
    assert map_severity("4").policy_version == SEVERITY_POLICY_VERSION


@pytest.mark.parametrize("value", ["", "0", "6", "x", None])
def test_severity_rejects_missing_or_out_of_range(value: str | None) -> None:
    with pytest.raises(ValueError):
        map_severity(value)


def test_status_normalizes_four_values_and_unknown_is_manual_review() -> None:
    assert normalize_status("Active").group == "pending_known"
    assert normalize_status("New").normalized == "new"
    assert normalize_status("Re-Opened").normalized == "reopened"
    assert normalize_status("Fixed").group == "fixed"
    unknown = normalize_status("Unexpected")
    assert unknown.normalized == "manual_review"
    assert unknown.manual_review is True
    assert unknown.policy_version == STATUS_POLICY_VERSION


def test_exploitability_positive_negative_and_indeterminate() -> None:
    positive = evaluate_exploitability(
        "Source: Synthetic\nReference: REF-1\nDescription: Synthetic\nLink: https://example.invalid"
    )
    assert positive.state == "positive"
    assert evaluate_exploitability("None").state == "negative_no_info"
    assert evaluate_exploitability("").state == "indeterminate"
    assert evaluate_exploitability("unstructured text").state == "indeterminate"


def test_malware_positive_requires_id_and_evidence() -> None:
    positive = evaluate_malware(
        "Source: Synthetic\nMalware ID: MAL-1\nType: Synthetic\nLink: https://example.invalid"
    )
    assert positive.state == "positive"
    assert evaluate_malware("N/A").state == "negative_no_info"
    assert evaluate_malware("").state == "indeterminate"
    assert evaluate_malware("Malware ID: MAL-1").state == "indeterminate"


def test_priority_only_when_both_indicators_are_positive() -> None:
    both = priority_for(
        evaluate_exploitability("Source: S\nReference: R"),
        evaluate_malware("Malware ID: M\nType: T"),
    )
    assert both == (True, "Explotabilidad positiva y malware positivo")
    one = priority_for(evaluate_exploitability("Source: S\nReference: R"), evaluate_malware(""))
    assert one == (False, None)
    assert PRIORITY_RULE_VERSION == "qualys-evidence-both-v1"
