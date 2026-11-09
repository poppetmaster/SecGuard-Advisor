"""Aceptación de la sección «Vulnerabilidades» con fixtures sintéticos.

La regresión automatizada usa el cliente ASGI con almacenamiento temporal. La
verificación de navegador real (teclado, foco, Escape, móvil y consola) se
ejecuta con Playwright MCP y se registra en `docs/evidencia/002-corte-5/`.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url
from secguard_advisor.db.models import QualysImport
from secguard_advisor.web.app import create_app

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "files"
ORIGIN = {"Origin": "http://testserver"}
HTMX = {**ORIGIN, "HX-Request": "true"}


def _client(tmp_path: Path) -> TestClient:
    settings = Settings(_env_file=None, storage_dir=tmp_path / "storage")
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    engine.dispose()
    return TestClient(create_app(settings, ollama_probe=lambda: True))


def _case(client: TestClient, title: str = "Caso UI") -> str:
    response = client.post("/cases", data={"title": title}, headers=ORIGIN, follow_redirects=False)
    return response.headers["location"].split("/")[-1]


def _upload(client: TestClient, case_id: str, filename: str):
    response = client.post(
        f"/cases/{case_id}/vulnerabilities/imports/validate",
        files={"file": (filename, (FIXTURES / filename).read_bytes(), "text/csv")},
        headers=HTMX,
    )
    redirect = response.headers.get("HX-Redirect")
    return client.get(redirect) if redirect else response


def _imports(client: TestClient, case_id: str) -> list[QualysImport]:
    with client.app.state.session_factory() as session:
        return list(
            session.scalars(
                select(QualysImport)
                .where(QualysImport.case_id == case_id)
                .order_by(QualysImport.created_at)
            )
        )


def _confirm(client: TestClient, case_id: str, import_id: str) -> None:
    response = client.post(
        f"/cases/{case_id}/vulnerabilities/imports/{import_id}/confirm",
        headers=HTMX,
    )
    assert response.status_code == 200


def test_vulnerabilities_acceptance_with_synthetic_fixtures(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        empty_case = _case(client, "Caso sin importaciones")
        empty = client.get(f"/cases/{empty_case}/vulnerabilities")
        assert "Sin importaciones confirmadas" in empty.text
        assert "Sin registros para estos filtros" not in empty.text

        case_id = _case(client)
        form_page = client.get(f"/cases/{case_id}/vulnerabilities/imports/new")
        assert 'data-form-key="qualys-validate"' in form_page.text
        assert "data-pending-text" in form_page.text

        preview = _upload(client, case_id, "qualys_synthetic_valid.csv")
        assert "Listo para confirmar" in preview.text
        first = _imports(client, case_id)[0]
        _confirm(client, case_id, first.id)

        second_preview = _upload(client, case_id, "qualys_synthetic_mixed.csv")
        assert "Listo para confirmar" in second_preview.text
        second = _imports(client, case_id)[1]
        _confirm(client, case_id, second.id)

        section = client.get(f"/cases/{case_id}/vulnerabilities")
        assert "Instantánea confirmada" in section.text
        assert "Historial" in section.text
        assert "Vulnerabilidades" in section.text

        historical = client.get(
            f"/cases/{case_id}/vulnerabilities",
            params={"import_id": first.id, "status_group": "fixed", "severity_level": "2"},
        )
        assert historical.status_code == 200
        assert "Histórica" in historical.text
        assert "Estado: Fixed" in historical.text
        assert "Severidad: Baja" in historical.text
        assert "Synthetic four" in historical.text
        assert f'name="import_id" value="{first.id}"' in historical.text

        priority = client.get(
            f"/cases/{case_id}/vulnerabilities",
            params={"import_id": first.id, "priority": "true"},
        )
        assert "Prioridad: Sí" in priority.text
        assert "Prioritaria: explotabilidad y malware" in priority.text
        assert "Synthetic one" in priority.text and "Synthetic two" in priority.text
        assert "Synthetic three" not in priority.text

        fixed = client.get(
            f"/cases/{case_id}/vulnerabilities",
            params={"import_id": second.id, "status_group": "fixed"},
        )
        assert "Antecedente prioritario; no es remediación pendiente." in fixed.text

        no_match = client.get(
            f"/cases/{case_id}/vulnerabilities",
            params={"import_id": first.id, "asset": "activo-inexistente"},
        )
        assert "Sin registros para estos filtros" in no_match.text
        assert "Sin importaciones confirmadas" not in no_match.text

        invalid = client.get(
            f"/cases/{case_id}/vulnerabilities",
            params={"import_id": first.id, "severity_level": "9"},
        )
        assert "La severidad debe estar entre 1 y 5" in invalid.text
        assert "Histórica" in invalid.text
        assert "qualys_synthetic_valid.csv" in invalid.text

        third = _upload(client, case_id, "qualys_synthetic_valid.csv")
        assert "ya estaba confirmada" in third.text
        assert len(_imports(client, case_id)) == 2
