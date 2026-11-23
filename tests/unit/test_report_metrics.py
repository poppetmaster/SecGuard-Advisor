"""Deterministic card and denominator metrics."""

from secguard_advisor.db.models import Case, QualysImport
from secguard_advisor.reports.dataset import build_dataset


def test_metrics_distinguish_statuses_and_indicators(report_context) -> None:
    with report_context.session_factory() as session:
        case = session.get(Case, report_context.case_id)
        snapshot = session.get(QualysImport, report_context.snapshot_id)
        dataset, _ = build_dataset(session, case=case, snapshot=snapshot)
    cards = dataset["cards"]
    assert dataset["base"]["total_rows"] == 10
    assert cards["pending"]["value"] == 8
    assert cards["critical_pending"]["value"] == 2
    assert cards["high_pending"]["value"] == 4
    assert cards["fixed"]["value"] == 1
    assert cards["manual_review"]["value"] == 3
    assert cards["distinct_assets_pending"]["value"] == 4
    assert cards["exploitability_positive_pending"]["value"] == 4
    assert cards["malware_positive_pending"]["value"] == 2
    assert cards["both_positive_pending"]["value"] == 2
    assert dataset["severity"]["denominator_pending"] == 8
    assert dataset["severity"]["denominator_fixed"] == 1
    assert dataset["assets_top"]["assets_with_critical_or_high"] == 4
    assert dataset["assets_top"]["records_critical_or_high"] == 6
    assert dataset["assets_top"]["recorted"] is False
    assert dataset["exploitability"]["denominator"] == 8


def test_multi_cve_rows_do_not_multiply_counts(report_context) -> None:
    with report_context.session_factory() as session:
        case = session.get(Case, report_context.case_id)
        snapshot = session.get(QualysImport, report_context.snapshot_id)
        dataset, _ = build_dataset(session, case=case, snapshot=snapshot)
    # The first fictional row has two CVEs but counts once.
    assert dataset["base"]["total_rows"] == 10
    assert dataset["cards"]["critical_pending"]["value"] == 2
