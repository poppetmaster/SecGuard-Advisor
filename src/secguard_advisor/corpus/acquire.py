"""Adquisición verificable del corpus público oficial."""

import hashlib
import io
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx
from pypdf import PdfReader

from secguard_advisor.config import Settings

MANIFEST_SCHEMA_VERSION = 1
MAX_SOURCE_BYTES = 50 * 1024 * 1024
USER_AGENT = "Mozilla/5.0 (compatible; SecGuardAdvisor/0.1; academic use)"


@dataclass(frozen=True, slots=True)
class SourceSpec:
    id: str
    title: str
    publisher: str
    published_at: str
    doi: str | None
    url: str
    license: str
    version_label: str
    marker: str


CORPUS_SOURCES = (
    SourceSpec(
        id="csf2",
        title="The NIST Cybersecurity Framework (CSF) 2.0",
        publisher="NIST",
        published_at="2024-02-26",
        doi="10.6028/NIST.CSWP.29",
        url="https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.29.pdf",
        license="U.S. Government work",
        version_label="NIST CSWP 29",
        marker="Cybersecurity Framework",
    ),
    SourceSpec(
        id="airmf",
        title="Artificial Intelligence Risk Management Framework (AI RMF 1.0)",
        publisher="NIST",
        published_at="2023-01-26",
        doi="10.6028/NIST.AI.100-1",
        url="https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf",
        license="U.S. Government work",
        version_label="NIST AI 100-1",
        marker="Artificial Intelligence Risk Management Framework",
    ),
    SourceSpec(
        id="ai6001",
        title="AI RMF: Generative Artificial Intelligence Profile",
        publisher="NIST",
        published_at="2024-07-26",
        doi="10.6028/NIST.AI.600-1",
        url="https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf",
        license="U.S. Government work",
        version_label="NIST AI 600-1",
        marker="Generative Artificial Intelligence Profile",
    ),
    SourceSpec(
        id="owasp-llm-2025",
        title="OWASP Top 10 for LLM Applications 2025",
        publisher="OWASP GenAI Security Project",
        published_at="2024-11-17",
        doi=None,
        url="https://genai.owasp.org/download/43299/?tmstv=1731900559",
        license="CC BY-SA 4.0",
        version_label="OWASP Top 10 for LLM Applications 2025",
        marker="OWASP Top 10",
    ),
)


@dataclass(frozen=True, slots=True)
class DownloadedSource:
    spec: SourceSpec
    data: bytes
    sha256: str
    size: int
    page_count: int
    marker_found: bool


@dataclass(frozen=True, slots=True)
class CorpusReport:
    sources: list[dict]
    failed: int


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _inspect_pdf(data: bytes, marker: str) -> tuple[int, bool]:
    reader = PdfReader(io.BytesIO(data))
    pages = list(reader.pages)
    marker_folded = marker.casefold()
    found = False
    for page in pages[:3]:
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        normalized = re.sub(r"\s+", " ", text)
        if marker_folded in normalized.casefold():
            found = True
            break
    return len(pages), found


def _download(client: httpx.Client, spec: SourceSpec) -> DownloadedSource:
    response = client.get(spec.url)
    response.raise_for_status()
    data = response.content
    if len(data) > MAX_SOURCE_BYTES:
        raise ValueError("La descarga excede el tamaño máximo permitido.")
    if not data.startswith(b"%PDF-"):
        raise ValueError("La respuesta no es un PDF.")
    page_count, marker_found = _inspect_pdf(data, spec.marker)
    return DownloadedSource(
        spec=spec,
        data=data,
        sha256=_sha256(data),
        size=len(data),
        page_count=page_count,
        marker_found=marker_found,
    )


def _load_manifest(path: Path) -> dict:
    if not path.exists():
        return {"schema_version": MANIFEST_SCHEMA_VERSION, "sources": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_manifest(path: Path, manifest: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == rendered:
        return
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(rendered, encoding="utf-8")
    temporary.replace(path)


def acquire_corpus(
    settings: Settings,
    *,
    client: httpx.Client | None = None,
    verify_only: bool = False,
    force_refresh: bool = False,
) -> CorpusReport:
    """Descarga, verifica y registra el corpus sin inventar hashes."""
    corpus_dir = settings.corpus_dir
    originals = corpus_dir / "originals"
    manifest_path = corpus_dir / "manifest.json"
    originals.mkdir(parents=True, exist_ok=True)

    manifest = _load_manifest(manifest_path)
    previous = {source["id"]: source for source in manifest.get("sources", [])}
    entries: list[dict] = []
    failed = 0

    owns_client = client is None
    http = client or httpx.Client(
        follow_redirects=True,
        timeout=60.0,
        headers={"User-Agent": USER_AGENT},
    )

    try:
        for spec in CORPUS_SOURCES:
            target = originals / f"{spec.id}.pdf"
            old = previous.get(spec.id, {})
            if verify_only:
                if target.exists() and old.get("sha256") == _sha256(target.read_bytes()):
                    data = target.read_bytes()
                    page_count, marker_found = _inspect_pdf(data, spec.marker)
                    if marker_found:
                        entry = {
                            **old,
                            "status": "verified",
                            "page_count": page_count,
                            "notes": None,
                        }
                    else:
                        entry = {
                            **old,
                            "status": "failed",
                            "notes": "El título esperado no aparece en el PDF local.",
                        }
                        failed += 1
                else:
                    entry = {
                        **old,
                        "status": "failed",
                        "notes": "Archivo local ausente o alterado.",
                    }
                    failed += 1
                entries.append(entry)
                continue

            if (
                not force_refresh
                and old.get("status") == "verified"
                and target.exists()
                and old.get("sha256") == _sha256(target.read_bytes())
            ):
                entries.append({**old, "status": "verified"})
                continue

            try:
                downloaded = _download(http, spec)
            except Exception as exc:
                failed += 1
                entries.append(
                    {
                        "id": spec.id,
                        "title": spec.title,
                        "publisher": spec.publisher,
                        "published_at": spec.published_at,
                        "doi": spec.doi,
                        "url": spec.url,
                        "license": spec.license,
                        "version_label": spec.version_label,
                        "retrieved_at": _now(),
                        "sha256": old.get("sha256"),
                        "bytes": old.get("bytes"),
                        "page_count": old.get("page_count"),
                        "status": "failed",
                        "notes": f"No se pudo adquirir: {type(exc).__name__}: {exc}",
                    }
                )
                continue

            if old.get("status") == "verified" and old.get("sha256") not in {
                None,
                downloaded.sha256,
            }:
                failed += 1
                entries.append(
                    {
                        **old,
                        "status": "failed",
                        "notes": (
                            "El archivo oficial cambió respecto del hash registrado; "
                            "se requiere revisión antes de reemplazarlo."
                        ),
                    }
                )
                continue

            target.write_bytes(downloaded.data)
            if not downloaded.marker_found:
                failed += 1
                status = "failed"
                notes = (
                    "El PDF se descargó pero el título esperado no aparece en las "
                    "primeras páginas; no se marca como verificado."
                )
            else:
                status = "verified"
                notes = None

            entries.append(
                {
                    "id": spec.id,
                    "title": spec.title,
                    "publisher": spec.publisher,
                    "published_at": spec.published_at,
                    "doi": spec.doi,
                    "url": spec.url,
                    "license": spec.license,
                    "version_label": spec.version_label,
                    "retrieved_at": _now(),
                    "sha256": downloaded.sha256,
                    "bytes": downloaded.size,
                    "page_count": downloaded.page_count,
                    "status": status,
                    "notes": notes,
                }
            )
    finally:
        if owns_client:
            http.close()

    unchanged = manifest.get("sources") == entries
    generated_at = manifest.get("generated_at") if unchanged else None
    _write_manifest(
        manifest_path,
        {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "generated_at": generated_at or _now(),
            "sources": entries,
        },
    )
    return CorpusReport(sources=entries, failed=failed)
