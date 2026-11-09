"""Pruebas de contrato de las rutas de «Vulnerabilidades»."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from tests.fixtures.qualys import make_row, write_csv

from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url
from secguard_advisor.db.models import QualysImport, QualysVulnerability
from secguard_advisor.web.app import create_app

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "files"
ORIGIN = {"Origin": "http://testserver"}
HTMX = {**ORIGIN, "HX-Request": "true"}


def _settings(tmp_path: Path, **overrides) -> Settings:
    return Settings(_env_file=None, storage_dir=tmp_path / "storage", **overrides)


def _prepare(settings: Settings) -> None:
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    engine.dispose()


@pytest.fixture
def client(tmp_path: Path):
    settings = _settings(tmp_path)
    _prepare(settings)
    app = create_app(settings, ollama_probe=lambda: True)
    with TestClient(app) as test_client:
        yield test_client


def _create_case(client: TestClient, title: str = "Caso vulnerabilidades") -> str:
    response = client.post(
        "/cases",
        data={"title": title},
        headers=ORIGIN,
        follow_redirects=False,
    )
    assert response.status_code == 303
    return response.headers["location"].split("/")[-1]


def _upload(client: TestClient, case_id: str, name: str, data: bytes):
    return client.post(
        f"/cases/{case_id}/vulnerabilities/imports/validate",
        files={"file": (name, data, "text/csv")},
        headers=HTMX,
    )


def _follow(client: TestClient, response):
    target = response.headers.get("HX-Redirect")
    assert target, response.text
    return client.get(target)


def _records(client: TestClient, case_id: str) -> list[QualysImport]:
    with client.app.state.session_factory() as session:
        return list(
            session.scalars(
                select(QualysImport)
                .where(QualysImport.case_id == case_id)
                .order_by(QualysImport.created_at)
            )
        )


def test_section_form_and_navigation(client) -> None:
    case_id = _create_case(client)
    section = client.get(f"/cases/{case_id}/vulnerabilities")
    form = client.get(f"/cases/{case_id}/vulnerabilities/imports/new")

    assert section.status_code == 200
    assert "Vulnerabilidades" in section.text
    assert "Sin importaciones confirmadas" in section.text
    assert f"/cases/{case_id}/vulnerabilities/imports/new" in section.text
    assert form.status_code == 200
    assert "Validar archivo" in form.text
    assert 'name="file"' in form.text
    assert 'name="manifest"' not in form.text
    assert 'name="path"' not in form.text


def test_valid_upload_preview_confirm_and_idempotency(client) -> None:
    case_id = _create_case(client)
    content = (FIXTURES / "qualys_synthetic_valid.csv").read_bytes()

    preview_response = _upload(client, case_id, "valid.csv", content)
    assert preview_response.status_code == 200
    preview = _follow(client, preview_response)
    assert "Listo para confirmar" in preview.text
    assert "Confirmar importación" in preview.text
    assert "Synthetic one" in preview.text
    records = _records(client, case_id)
    assert len(records) == 1
    import_id = records[0].id
    assert records[0].status == "staged"

    confirmed = client.post(
        f"/cases/{case_id}/vulnerabilities/imports/{import_id}/confirm",
        headers=HTMX,
    )
    assert confirmed.status_code == 200
    confirmed_page = _follow(client, confirmed)
    assert confirmed_page.status_code == 200
    assert "Importación confirmada" in confirmed_page.text
    assert _records(client, case_id)[0].status == "confirmed"

    again = client.post(
        f"/cases/{case_id}/vulnerabilities/imports/{import_id}/confirm",
        headers=HTMX,
    )
    assert again.status_code == 200
    assert "/vulnerabilities?notice=idempotent" in again.headers.get("HX-Redirect", "")
    again_page = _follow(client, again)
    assert "ya estaba confirmada" in again_page.text

    section = client.get(f"/cases/{case_id}/vulnerabilities")
    assert section.status_code == 200
    assert "Instantánea confirmada" in section.text
    assert "Synthetic one" in section.text
    assert "Alta" in section.text
    assert "<script>alert" not in section.text


def test_rejected_empty_and_invalid_header_cannot_confirm(client) -> None:
    case_id = _create_case(client)
    invalid_rows_response = _upload(
        client,
        case_id,
        "invalid.csv",
        (FIXTURES / "qualys_synthetic_invalid_rows.csv").read_bytes(),
    )
    invalid_rows = _follow(client, invalid_rows_response)
    assert "Rechazado" in invalid_rows.text
    assert "invalid_severity" in invalid_rows.text
    assert "Confirmar importación" not in invalid_rows.text

    empty_response = _upload(client, case_id, "empty.csv", b"")
    empty = _follow(client, empty_response)
    assert "Rechazado" in empty.text
    assert "El archivo está vacío" in empty.text

    header_response = _upload(
        client,
        case_id,
        "header.csv",
        (FIXTURES / "qualys_synthetic_invalid_header.csv").read_bytes(),
    )
    header = _follow(client, header_response)
    assert "header_mismatch" in header.text

    records = _records(client, case_id)
    assert {record.status for record in records} == {"rejected"}
    with client.app.state.session_factory() as session:
        assert session.scalar(select(QualysVulnerability).limit(1)) is None


def test_oversized_and_invalid_extension(tmp_path: Path) -> None:
    settings = _settings(tmp_path, qualys_max_bytes=20)
    _prepare(settings)
    app = create_app(settings, ollama_probe=lambda: True)
    with TestClient(app) as client:
        case_id = _create_case(client)
        oversized = _upload(
            client,
            case_id,
            "valid.csv",
            (FIXTURES / "qualys_synthetic_valid.csv").read_bytes(),
        )
        assert oversized.status_code == 413
        assert "supera el tamaño" in oversized.text

        wrong = client.post(
            f"/cases/{case_id}/vulnerabilities/imports/validate",
            files={"file": ("report.txt", b"x", "text/plain")},
            headers=HTMX,
        )
        assert wrong.status_code == 422
        assert "Solo se admite" in wrong.text


def test_cancel_keeps_current_snapshot(client) -> None:
    case_id = _create_case(client)
    first = _upload(
        client,
        case_id,
        "first.csv",
        (FIXTURES / "qualys_synthetic_valid.csv").read_bytes(),
    )
    assert first.status_code == 200
    first_id = _records(client, case_id)[0].id
    client.post(
        f"/cases/{case_id}/vulnerabilities/imports/{first_id}/confirm",
        headers=HTMX,
    )

    second = _upload(
        client,
        case_id,
        "second.csv",
        (FIXTURES / "qualys_synthetic_second.csv").read_bytes(),
    )
    assert second.status_code == 200
    second_id = next(record.id for record in _records(client, case_id) if record.id != first_id)
    cancelled = client.post(
        f"/cases/{case_id}/vulnerabilities/imports/{second_id}/cancel",
        headers=HTMX,
    )
    assert cancelled.status_code == 200
    cancelled_page = _follow(client, cancelled)
    assert "no cambió" in cancelled_page.text

    section = client.get(f"/cases/{case_id}/vulnerabilities")
    assert "Instantánea confirmada" in section.text
    assert "#1" in section.text
    with client.app.state.session_factory() as session:
        first_record = session.get(QualysImport, first_id)
        second_record = session.get(QualysImport, second_id)
        assert first_record.status == "confirmed"
        assert second_record.status == "cancelled"


def test_case_isolation(client) -> None:
    case_a = _create_case(client, "Caso A")
    case_b = _create_case(client, "Caso B")
    preview = _upload(
        client,
        case_a,
        "a.csv",
        (FIXTURES / "qualys_synthetic_valid.csv").read_bytes(),
    )
    assert preview.status_code == 200
    import_id = _records(client, case_a)[0].id

    assert client.get(f"/cases/{case_b}/vulnerabilities/imports/{import_id}").status_code == 404
    assert (
        client.post(
            f"/cases/{case_b}/vulnerabilities/imports/{import_id}/confirm",
            headers=HTMX,
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/cases/{case_b}/vulnerabilities/imports/{import_id}/cancel",
            headers=HTMX,
        ).status_code
        == 404
    )
    assert import_id not in client.get(f"/cases/{case_b}/vulnerabilities").text


def test_csv_content_is_escaped_and_results_not_rendered(client, tmp_path: Path) -> None:
    case_id = _create_case(client)
    row = make_row(
        QID="930001",
        IP="10.0.9.1",
        FQDN="safe.example",
        Title="<script>alert(1)</script>",
        Results="<script>evil()</script>",
    )
    path = tmp_path / "unsafe.csv"
    content = write_csv(path, [row])
    preview = _follow(client, _upload(client, case_id, "unsafe.csv", content))
    assert preview.status_code == 200
    import_id = _records(client, case_id)[0].id
    client.post(
        f"/cases/{case_id}/vulnerabilities/imports/{import_id}/confirm",
        headers=HTMX,
    )
    section = client.get(f"/cases/{case_id}/vulnerabilities")
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in section.text
    assert "<script>alert(1)</script>" not in section.text
    assert "evil()" not in section.text
