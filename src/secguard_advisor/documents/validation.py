"""Validación de archivos de evidencia del caso."""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from fastapi import UploadFile

ALLOWED_EXTENSIONS = {
    ".pdf": "application/pdf",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
}
_CHUNK_SIZE = 1024 * 1024


class DocumentValidationError(Exception):
    """Archivo rechazado con un código y un mensaje para el usuario."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class UploadedContent:
    filename: str
    content_type: str
    data: bytes
    sha256: str
    size: int
    extension: str


def sha256_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def sanitize_filename(filename: str) -> str:
    """Reduce el nombre a su componente final y rechaza rutas."""
    name = (filename or "").replace("\\", "/").split("/")[-1].strip()
    if not name or name in {".", ".."}:
        raise DocumentValidationError("validation_error", "El archivo no tiene un nombre válido.")
    return name[:255]


def validate_bytes(filename: str, data: bytes, max_bytes: int) -> UploadedContent:
    """Valida extensión, tamaño y contenido real."""
    safe_name = sanitize_filename(filename)
    extension = Path(safe_name).suffix.lower()
    content_type = ALLOWED_EXTENSIONS.get(extension)
    if content_type is None:
        raise DocumentValidationError(
            "unsupported_media_type",
            "Solo se admiten PDF con texto y Markdown.",
        )

    if not data:
        raise DocumentValidationError("validation_error", "El archivo está vacío.")
    if len(data) > max_bytes:
        raise DocumentValidationError(
            "payload_too_large",
            "El archivo supera el tamaño permitido.",
        )

    if extension == ".pdf":
        if not data.startswith(b"%PDF-"):
            raise DocumentValidationError(
                "unsupported_media_type",
                "El contenido no corresponde a un PDF.",
            )
    else:
        if b"\x00" in data:
            raise DocumentValidationError(
                "unsupported_media_type",
                "El contenido no corresponde a un Markdown de texto.",
            )
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DocumentValidationError(
                "unsupported_media_type",
                "El Markdown no está codificado en UTF-8.",
            ) from exc

    return UploadedContent(
        filename=safe_name,
        content_type=content_type,
        data=data,
        sha256=sha256_bytes(data),
        size=len(data),
        extension=extension,
    )


def read_upload(upload: UploadFile, max_bytes: int) -> UploadedContent:
    """Lee el archivo por bloques y lo valida."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = upload.file.read(_CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise DocumentValidationError(
                "payload_too_large",
                "El archivo supera el tamaño permitido.",
            )
        chunks.append(chunk)

    return validate_bytes(upload.filename or "", b"".join(chunks), max_bytes)
