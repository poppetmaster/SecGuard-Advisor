"""Pruebas de contrato de documentos."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from tests.fixtures.fakes import FakeEmbedder, FakeIndex

from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url
from secguard_advisor.db.models import Document, DocumentChunk, DocumentVersion
from secguard_advisor.web.app import create_app

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "files"
ORIGIN = {"Origin": "http://testserver"}
HTMX = {**ORIGIN, "HX-Request": "true"}


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        storage_dir=tmp_path / "storage",
        max_upload_mb=1,
    )


def _prepare(settings: Settings) -> None:
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    engine.dispose()


@pytest.fixture
def client(tmp_path: Path):
    settings = _settings(tmp_path)
    _prepare(settings)
    index = FakeIndex()
    app = create_app(
        settings,
        ollama_probe=lambda: True,
        embedder_factory=lambda: FakeEmbedder(),
        index_factory=lambda: index,
    )
    with TestClient(app) as test_client:
        yield test_client


def _create_case(client: TestClient, title: str = "Caso documental") -> str:
    response = client.post(
        "/cases",
        data={"title": title},
        headers=ORIGIN,
        follow_redirects=False,
    )
    assert response.status_code == 303
    return response.headers["location"].split("/")[-1]


def _upload(
    client: TestClient,
    case_id: str,
    filename: str,
    data: bytes,
    content_type: str,
    *,
    headers=None,
):
    return client.post(
        f"/cases/{case_id}/documents",
        files={"file": (filename, data, content_type)},
        data={"title": "Documento"},
        headers=headers or HTMX,
    )


def _document_records(client: TestClient, case_id: str):
    with client.app.state.session_factory() as session:
        document = session.scalar(select(Document).where(Document.case_id == case_id))
        version = session.scalar(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document.id)
            .order_by(DocumentVersion.version_number.desc())
        )
        chunks = list(
            session.scalars(select(DocumentChunk).where(DocumentChunk.version_id == version.id))
        )
        return document, version, chunks


def test_upload_and_detail(client) -> None:
    case_id = _create_case(client)

    response = _upload(
        client,
        case_id,
        "doc.pdf",
        (FIXTURES / "sample.pdf").read_bytes(),
        "application/pdf",
    )

    assert response.status_code == 201
    assert "Disponible" in response.text

    document, version, chunks = _document_records(client, case_id)
    assert version.status == "available"
    assert chunks

    detail = client.get(f"/cases/{case_id}/documents/{document.id}")
    assert detail.status_code == 200
    assert "Versiones" in detail.text
    assert "Fragmentos" in detail.text

    case_page = client.get(f"/cases/{case_id}")
    assert case_page.status_code == 200
    assert "Documentos" in case_page.text

    fragment = client.get(
        f"/cases/{case_id}/documents/{document.id}/versions/{version.id}/fragments/{chunks[0].id}",
        params={"quote": chunks[0].text[:8]},
    )
    assert fragment.status_code == 200
    assert "<mark" in fragment.text


def test_duplicate_upload_is_conflict(client) -> None:
    case_id = _create_case(client)
    data = (FIXTURES / "sample.pdf").read_bytes()

    first = _upload(client, case_id, "doc.pdf", data, "application/pdf")
    second = _upload(client, case_id, "doc.pdf", data, "application/pdf")

    assert first.status_code == 201
    assert second.status_code == 409
    assert "ya existe" in second.text


def test_invalid_type_is_rejected(client) -> None:
    case_id = _create_case(client)

    response = _upload(client, case_id, "script.exe", b"contenido", "application/octet-stream")

    assert response.status_code == 415


def test_empty_file_is_rejected(client) -> None:
    case_id = _create_case(client)

    response = _upload(client, case_id, "vacio.pdf", b"", "application/pdf")

    assert response.status_code == 422


def test_oversized_file_is_rejected(client) -> None:
    case_id = _create_case(client)

    response = _upload(
        client,
        case_id,
        "grande.pdf",
        b"%PDF-" + b"x" * 1_100_000,
        "application/pdf",
    )

    assert response.status_code == 413


def test_unknown_case_is_rejected(client) -> None:
    response = _upload(
        client,
        "0" * 32,
        "doc.pdf",
        (FIXTURES / "sample.pdf").read_bytes(),
        "application/pdf",
    )

    assert response.status_code == 404


def test_case_isolation(client) -> None:
    case_a = _create_case(client, "Caso A")
    case_b = _create_case(client, "Caso B")
    _upload(client, case_a, "a.pdf", (FIXTURES / "sample.pdf").read_bytes(), "application/pdf")
    document, _version, _chunks = _document_records(client, case_a)

    detail = client.get(f"/cases/{case_b}/documents/{document.id}")
    panel = client.get(f"/cases/{case_b}/documents")

    assert detail.status_code == 404
    assert document.id not in panel.text


def test_blank_pdf_is_no_usable_text(client) -> None:
    case_id = _create_case(client)

    response = _upload(
        client,
        case_id,
        "blank.pdf",
        (FIXTURES / "blank.pdf").read_bytes(),
        "application/pdf",
    )

    assert response.status_code == 201
    assert "Sin texto" in response.text


def test_retry_after_embedding_failure(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _prepare(settings)
    embedders = [FakeEmbedder(fail=True), FakeEmbedder()]
    index = FakeIndex()
    app = create_app(
        settings,
        ollama_probe=lambda: True,
        embedder_factory=lambda: embedders.pop(0),
        index_factory=lambda: index,
    )
    with TestClient(app) as client:
        case_id = _create_case(client)
        failed = _upload(
            client,
            case_id,
            "doc.pdf",
            (FIXTURES / "sample.pdf").read_bytes(),
            "application/pdf",
        )
        assert failed.status_code == 500
        document, _version, _chunks = _document_records(client, case_id)

        retry = client.post(
            f"/cases/{case_id}/documents/{document.id}/retry",
            headers=HTMX,
        )

    assert retry.status_code == 202
    assert "Disponible" in retry.text
