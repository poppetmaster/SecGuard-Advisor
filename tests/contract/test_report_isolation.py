"""Case isolation for reports and snapshots."""

from fastapi.testclient import TestClient

from secguard_advisor.db.models import Case
from secguard_advisor.web.app import create_app


def test_report_of_other_case_returns_404(report_context) -> None:
    with TestClient(create_app(report_context.settings, ollama_probe=lambda: False)) as client:
        with client.app.state.session_factory() as session:
            other = Case(title="Otro caso", synthetic_notice="Sintético")
            session.add(other)
            session.commit()
            other_id = other.id
        response = client.get(f"/cases/{other_id}/reports/does-not-exist/versions/1")
        assert response.status_code == 404
