"""Report routes, validation and PDF download."""

import pytest
from fastapi.testclient import TestClient

import secguard_advisor.web.routes.reports as report_routes
from secguard_advisor.db.models import Case
from secguard_advisor.reports.service import create_report_version
from secguard_advisor.web.app import create_app


def _fake_charts(_settings, charts):
    return {key: f"<svg>{key}</svg>" for key in charts}


def _fake_pdf(_settings, _html, path):
    data = b"%PDF-1.4\n% fictional\n%%EOF\n"
    path.write_bytes(data)
    return data


@pytest.fixture
def client(report_context, monkeypatch):
    def _create(session, settings, **kwargs):
        return create_report_version(
            session,
            settings,
            chart_renderer=_fake_charts,
            pdf_renderer=_fake_pdf,
            **kwargs,
        )

    monkeypatch.setattr(report_routes, "create_report_version", _create)
    with TestClient(create_app(report_context.settings, ollama_probe=lambda: False)) as value:
        yield value


def test_reports_routes_and_pdf(client, report_context) -> None:
    new_page = client.get(f"/cases/{report_context.case_id}/reports/new")
    assert new_page.status_code == 200
    assert "Instantánea Qualys confirmada" in new_page.text

    response = client.post(
        f"/cases/{report_context.case_id}/reports",
        data={"snapshot_id": report_context.snapshot_id, "author": "Prueba"},
        headers={"Origin": "http://testserver"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert "/versions/1" in location

    view = client.get(location)
    assert view.status_code == 200
    assert "Informe ejecutivo" in view.text
    assert "Registros pendientes" in view.text
    assert "data-echarts" in view.text

    pdf = client.get(location + "/pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")

    preview = client.get(location + "/preview")
    assert preview.status_code == 200
    assert "Informe ejecutivo de vulnerabilidades" in preview.text

    history = client.get(f"/cases/{report_context.case_id}/reports")
    assert history.status_code == 200
    assert "Historial de versiones" in history.text


def test_invalid_snapshot_is_422(client, report_context) -> None:
    response = client.post(
        f"/cases/{report_context.case_id}/reports",
        data={"snapshot_id": "no-existe", "author": "Prueba"},
        headers={"Origin": "http://testserver"},
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert "instantánea" in response.text.lower()


def test_other_case_is_not_visible(client, report_context) -> None:
    with client.app.state.session_factory() as session:
        other = Case(title="Otro caso", synthetic_notice="Sintético")
        session.add(other)
        session.commit()
        other_id = other.id
    response = client.get(f"/cases/{other_id}/reports")
    assert response.status_code == 200
    assert "Sin importaciones confirmadas" in response.text
