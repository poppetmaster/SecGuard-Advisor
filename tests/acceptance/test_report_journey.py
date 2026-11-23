"""End-to-end Corte A journey with a fictional confirmed snapshot."""

from __future__ import annotations

from fastapi.testclient import TestClient

from secguard_advisor.db.models import ReportArtifact
from secguard_advisor.web.app import create_app


def test_report_journey_from_confirmed_snapshot(report_context) -> None:
    with TestClient(create_app(report_context.settings, ollama_probe=lambda: False)) as client:
        reports = client.get(f"/cases/{report_context.case_id}/reports")
        assert reports.status_code == 200
        assert "Informe ejecutivo" in reports.text

        form = client.get(f"/cases/{report_context.case_id}/reports/new")
        assert form.status_code == 200
        assert report_context.snapshot_id in form.text

        created = client.post(
            f"/cases/{report_context.case_id}/reports",
            data={"snapshot_id": report_context.snapshot_id, "author": "Recorrido A"},
            headers={"Origin": "http://testserver"},
            follow_redirects=False,
        )
        assert created.status_code == 303
        location = created.headers["location"]

        view = client.get(location)
        assert view.status_code == 200
        assert "Resumen ejecutivo" in view.text
        assert "Registros pendientes" in view.text
        assert "Fixed" in view.text
        assert "Requieren revisión" in view.text
        assert "data-echarts" in view.text
        assert "Historial de versiones" in view.text

        preview = client.get(location + "/preview")
        assert preview.status_code == 200
        assert "Informe ejecutivo de vulnerabilidades" in preview.text
        assert "Caso reservado" in preview.text

        pdf = client.get(location + "/pdf")
        assert pdf.status_code == 200
        assert pdf.content.startswith(b"%PDF")

        with client.app.state.session_factory() as session:
            version = session.query(ReportArtifact).count()
        assert version >= 5  # PDF + four SVG charts
