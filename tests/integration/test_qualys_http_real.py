"""Probe HTTP local del CSV real filtrado, sin modelo ni servicios externos."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url
from secguard_advisor.db.models import QualysImport, QualysVulnerability
from secguard_advisor.vulnerabilities.validation import validate_csv
from secguard_advisor.web.app import create_app

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = ROOT.parent / "14-Qualys_Hallazgos_Active_New_ReOpened.csv"
MANIFEST_PATH = ROOT.parent / "14-Qualys_Hallazgos_Active_New_ReOpened_manifest.json"
ORIGIN = {"Origin": "http://testserver"}
HTMX = {**ORIGIN, "HX-Request": "true"}


def test_real_csv_http_flow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if not CSV_PATH.exists() or not MANIFEST_PATH.exists():
        pytest.skip("El CSV real o su manifiesto no están disponibles localmente.")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    settings = Settings(_env_file=None, storage_dir=tmp_path / "storage")
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    engine.dispose()
    app = create_app(settings, ollama_probe=lambda: True)
    with TestClient(app) as client:
        created = client.post(
            "/cases",
            data={"title": "Probe HTTP Qualys"},
            headers=ORIGIN,
            follow_redirects=False,
        )
        assert created.status_code == 303
        case_id = created.headers["location"].split("/")[-1]

        content = CSV_PATH.read_bytes()
        validation = validate_csv(content, settings=settings, manifest_path=MANIFEST_PATH)
        assert validation.status == "staged"
        assert validation.manifest.status == "matched"
        assert validation.row_count == 662

        preview_response = client.post(
            f"/cases/{case_id}/vulnerabilities/imports/validate",
            files={"file": (CSV_PATH.name, content, "text/csv")},
            headers=HTMX,
        )
        assert preview_response.status_code == 200
        preview_url = preview_response.headers["HX-Redirect"]
        preview = client.get(preview_url)
        assert preview.status_code == 200
        assert "Listo para confirmar" in preview.text
        assert "662" in preview.text

        with client.app.state.session_factory() as session:
            record = session.scalar(select(QualysImport).where(QualysImport.case_id == case_id))
            assert record.status == "staged"
            import_id = record.id
        confirmed = client.post(
            f"/cases/{case_id}/vulnerabilities/imports/{import_id}/confirm",
            headers=HTMX,
        )
        assert confirmed.status_code == 200
        section = client.get(confirmed.headers["HX-Redirect"])
        assert "Importación confirmada" in section.text

        section = client.get(f"/cases/{case_id}/vulnerabilities")
        assert section.status_code == 200
        assert "662" in section.text
        with client.app.state.session_factory() as session:
            records = list(
                session.scalars(select(QualysImport).where(QualysImport.case_id == case_id))
            )
            assert len(records) == 1
            assert records[0].status == "confirmed"
            rows = session.scalar(
                select(func.count())
                .select_from(QualysVulnerability)
                .where(QualysVulnerability.import_id == import_id)
            )
            assert rows == 662

        repeated = client.post(
            f"/cases/{case_id}/vulnerabilities/imports/validate",
            files={"file": (CSV_PATH.name, content, "text/csv")},
            headers=HTMX,
        )
        assert repeated.status_code == 200
        repeated_page = client.get(repeated.headers["HX-Redirect"])
        assert "ya estaba confirmada" in repeated_page.text
        with client.app.state.session_factory() as session:
            records = list(
                session.scalars(select(QualysImport).where(QualysImport.case_id == case_id))
            )
            assert len(records) == 1
            assert records[0].id == import_id
