"""ECharts option and conclusion contract."""

from secguard_advisor.db.models import Case, QualysImport
from secguard_advisor.reports.charts import build_chart_specs
from secguard_advisor.reports.dataset import build_dataset


def test_charts_are_serializable_and_have_conclusions(report_context) -> None:
    with report_context.session_factory() as session:
        case = session.get(Case, report_context.case_id)
        snapshot = session.get(QualysImport, report_context.snapshot_id)
        dataset, _ = build_dataset(session, case=case, snapshot=snapshot)
    charts = build_chart_specs(dataset)
    assert set(charts) >= {"severity", "assets", "exploitability", "malware"}
    for key in ("severity", "assets", "exploitability", "malware"):
        assert charts[key]["title"]
        assert charts[key]["conclusion"]
        assert charts[key]["option"]["animation"] is False
        assert charts[key]["option"].get("series")
    assert charts["severity"]["option"]["series"][0]["name"] == "Pendientes"
    assert "severidad 3 o superior" in charts["severity"]["conclusion"]
    assert charts["assets"]["option"]["yAxis"]["type"] == "category"
