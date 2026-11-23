"""Web and PDF consume the same persisted dataset and chart specs."""

from __future__ import annotations

import io
import re

from pypdf import PdfReader
from sqlalchemy import select

from secguard_advisor.db.models import ReportArtifact
from secguard_advisor.reports.canonical import parse_json
from secguard_advisor.reports.service import create_report_version, get_version, preview_html


def test_cards_charts_and_snapshot_are_concordant(report_context) -> None:
    with report_context.session_factory() as session:
        result = create_report_version(
            session,
            report_context.settings,
            case_id=report_context.case_id,
            snapshot_id=report_context.snapshot_id,
            author="Prueba concordancia",
            synthesize=False,
        )
        session.commit()
        version = get_version(
            session, report_context.case_id, result.report_id, result.version_number
        )
        dataset = parse_json(version.dataset_json)
        charts = parse_json(version.chart_specs_json)
        html = preview_html(session, report_context.settings, version)
        artifact = session.scalar(
            select(ReportArtifact).where(
                ReportArtifact.report_version_id == version.id,
                ReportArtifact.kind == "pdf",
            )
        )
        pdf_bytes = (report_context.settings.reports_dir / artifact.relative_path).read_bytes()
    pdf_text = "\n".join(
        page.extract_text() or "" for page in PdfReader(io.BytesIO(pdf_bytes)).pages
    )
    pdf_flat = re.sub(r"\s+", " ", pdf_text).strip()

    for key in ("pending", "critical_pending", "high_pending", "fixed", "manual_review"):
        value = dataset["cards"][key]["value"]
        assert str(value) in html
        assert str(value) in pdf_text
    for key in ("severity", "assets", "exploitability", "malware"):
        assert charts[key]["title"] in html
        assert charts[key]["title"] in pdf_flat
        assert charts[key]["conclusion"] in html
    assert dataset["assets_top"]["items"][0]["alias"] in html
    assert dataset["assets_top"]["items"][0]["alias"] in pdf_flat
    assert str(dataset["snapshot"]["sequence"]) in html
    assert str(dataset["snapshot"]["sequence"]) in pdf_flat
    assert dataset["cards"]["fixed"]["value"] == 1
    assert dataset["cards"]["manual_review"]["value"] == 3
