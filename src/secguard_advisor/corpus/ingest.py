"""Ingesta del corpus público compartido."""

import json

from sqlalchemy.orm import Session, sessionmaker

from secguard_advisor.config import Settings
from secguard_advisor.documents.service import IngestionOutcome, ingest_document
from secguard_advisor.documents.validation import validate_bytes


def load_manifest(settings: Settings) -> list[dict]:
    path = settings.corpus_dir / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"No existe el manifiesto: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return list(payload.get("sources", []))


def ingest_public_corpus(
    factory: sessionmaker[Session],
    settings: Settings,
    *,
    embedder,
    index,
) -> list[IngestionOutcome]:
    """Ingesta las fuentes verificadas como documentos públicos sin caso."""
    outcomes: list[IngestionOutcome] = []

    for source in load_manifest(settings):
        source_id = source.get("id", "")
        if source.get("status") != "verified":
            outcomes.append(
                IngestionOutcome(
                    status="skipped",
                    document_id="",
                    version_id="",
                    version_number=0,
                    chunks=0,
                    message=f"Fuente no verificada: {source_id}",
                )
            )
            continue

        original = settings.corpus_dir / "originals" / f"{source_id}.pdf"
        if not original.exists():
            outcomes.append(
                IngestionOutcome(
                    status="skipped",
                    document_id="",
                    version_id="",
                    version_number=0,
                    chunks=0,
                    message=f"Original ausente: {source_id}",
                )
            )
            continue

        data = original.read_bytes()
        upload = validate_bytes(
            f"{source_id}.pdf",
            data,
            settings.max_upload_bytes,
        )
        if upload.sha256 != source.get("sha256"):
            outcomes.append(
                IngestionOutcome(
                    status="failed",
                    document_id="",
                    version_id="",
                    version_number=0,
                    chunks=0,
                    message=f"El hash de {source_id} no coincide con el manifiesto.",
                )
            )
            continue

        outcomes.append(
            ingest_document(
                factory,
                settings,
                scope_key=f"public:{source_id}",
                case_id=None,
                origin="public_corpus",
                source_id=source_id,
                title=source.get("title") or source_id,
                upload=upload,
                embedder=embedder,
                index=index,
                declared_version=source.get("version_label"),
                retrieved_at=source.get("retrieved_at"),
                license=source.get("license"),
                store_original_file=False,
            )
        )

    return outcomes
