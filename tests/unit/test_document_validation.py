"""Pruebas de validación y almacenamiento de archivos."""

from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile

from secguard_advisor.config import Settings
from secguard_advisor.documents.storage import (
    original_path,
    read_original,
    store_original,
)
from secguard_advisor.documents.validation import (
    DocumentValidationError,
    read_upload,
    sanitize_filename,
    validate_bytes,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


def _pdf() -> bytes:
    return (FIXTURES / "sample.pdf").read_bytes()


def test_valid_pdf_is_accepted() -> None:
    content = validate_bytes("documento.pdf", _pdf(), 10_000_000)

    assert content.filename == "documento.pdf"
    assert content.content_type == "application/pdf"
    assert content.extension == ".pdf"
    assert len(content.sha256) == 64
    assert content.size == len(_pdf())


def test_valid_markdown_is_accepted() -> None:
    content = validate_bytes(
        "notas.md",
        (FIXTURES / "sample.md").read_bytes(),
        10_000_000,
    )

    assert content.content_type == "text/markdown"
    assert content.extension == ".md"


def test_pdf_extension_with_fake_content_is_rejected() -> None:
    with pytest.raises(DocumentValidationError) as captured:
        validate_bytes("documento.pdf", b"no es un pdf", 10_000_000)

    assert captured.value.code == "unsupported_media_type"


def test_unsupported_extension_is_rejected() -> None:
    with pytest.raises(DocumentValidationError) as captured:
        validate_bytes("script.exe", b"contenido", 10_000_000)

    assert captured.value.code == "unsupported_media_type"


def test_empty_file_is_rejected() -> None:
    with pytest.raises(DocumentValidationError) as captured:
        validate_bytes("documento.pdf", b"", 10_000_000)

    assert captured.value.code == "validation_error"


def test_oversized_file_is_rejected() -> None:
    with pytest.raises(DocumentValidationError) as captured:
        validate_bytes("documento.pdf", _pdf(), max_bytes=10)

    assert captured.value.code == "payload_too_large"


def test_filename_is_sanitized() -> None:
    assert sanitize_filename("../../evil.pdf") == "evil.pdf"
    assert sanitize_filename("carpeta\\documento.pdf") == "documento.pdf"

    with pytest.raises(DocumentValidationError):
        sanitize_filename("..")


def test_upload_is_read_in_chunks() -> None:
    upload = UploadFile(filename="documento.pdf", file=BytesIO(_pdf()))

    content = read_upload(upload, 10_000_000)

    assert content.size == len(_pdf())


def test_original_storage_is_content_addressed_and_idempotent(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, storage_dir=tmp_path / "storage")
    settings.ensure_directories()
    content = validate_bytes("documento.pdf", _pdf(), 10_000_000)

    first = store_original(settings, content)
    second = store_original(settings, content)

    assert first == second
    assert first.name == f"{content.sha256}.pdf"
    assert first.is_relative_to(settings.originals_dir)
    assert read_original(settings, content.sha256, content.extension) == _pdf()


def test_invalid_hash_cannot_escape_storage(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, storage_dir=tmp_path / "storage")

    with pytest.raises(ValueError):
        original_path(settings, "../../etc/passwd", ".pdf")
