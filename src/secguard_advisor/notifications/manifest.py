"""Canonical approved-content manifest for Telegram delivery."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from secguard_advisor.db.models import ContactChannel, ReportArtifact, ReportVersion
from secguard_advisor.notifications.contacts import mask_chat_id
from secguard_advisor.notifications.errors import NotificationError
from secguard_advisor.reports.canonical import canonical_json, canonical_sha256, parse_json
from secguard_advisor.reports.errors import report_error

CONTENT_FIELDS = (
    "schema_version",
    "case_id",
    "report_id",
    "report_version_id",
    "report_version_number",
    "dataset_sha256",
    "outbound_text",
    "outbound_text_sha256",
    "pdf_sha256",
    "content_policy",
)


def _pdf_artifact(session: Session, version: ReportVersion) -> ReportArtifact:
    artifact = session.scalar(
        select(ReportArtifact).where(
            ReportArtifact.report_version_id == version.id,
            ReportArtifact.kind == "pdf",
        )
    )
    if artifact is None:
        raise report_error("pdf_not_ready")
    return artifact


def build_outbound_text(dataset: dict[str, Any], version: ReportVersion) -> str:
    cards = dataset["cards"]
    assets = dataset.get("assets_top", {}).get("items", [])
    asset_line = ", ".join(item["alias"] for item in assets[:5]) or "Sin activos destacados"
    return (
        f"SecGuard Advisor · Informe ejecutivo v{version.version_number}\n"
        f"Instantánea Qualys #{dataset['snapshot']['sequence']}\n"
        f"Pendientes: {cards['pending']['value']} · Críticas: "
        f"{cards['critical_pending']['value']} · Altas: {cards['high_pending']['value']}\n"
        f"Activos destacados: {asset_line}\n"
        f"Explotabilidad positiva: {cards['exploitability_positive_pending']['value']} · "
        f"Malware positivo: {cards['malware_positive_pending']['value']}\n"
        "El PDF adjunto contiene el informe completo. Los indicadores vacíos no equivalen a "
        "ausencia de amenaza."
    )


def _recipients(session: Session, contact_ids: list[str]) -> list[dict[str, Any]]:
    recipients = []
    for contact_id in contact_ids:
        contact = session.get(ContactChannel, contact_id)
        if contact is None:
            raise NotificationError("contact_not_found", "El contacto no existe.")
        recipients.append(
            {
                "contact_id": contact.id,
                "alias": contact.alias,
                "masked_chat": mask_chat_id(contact.chat_id),
                "chat_fingerprint": contact.chat_fingerprint,
            }
        )
    return recipients


def _payload(session: Session, version: ReportVersion, contact_ids: list[str]) -> dict[str, Any]:
    if version.status != "ready":
        raise report_error("version_not_found")
    dataset = parse_json(version.dataset_json)
    pdf = _pdf_artifact(session, version)
    recipients = _recipients(session, contact_ids)
    outbound_text = build_outbound_text(dataset, version)
    return {
        "schema_version": "report-manifest-v1",
        "case_id": version.case_id,
        "report_id": version.report_id,
        "report_version_id": version.id,
        "report_version_number": version.version_number,
        "dataset_sha256": version.dataset_sha256,
        "outbound_text": outbound_text,
        "outbound_text_sha256": canonical_sha256(outbound_text),
        "pdf_sha256": pdf.sha256,
        "content_policy": dataset.get("content_policy", {}),
        "recipients": recipients,
        "recipients_sha256": canonical_sha256(recipients),
    }


def build_manifest(
    session: Session,
    version: ReportVersion,
    contact_ids: list[str],
) -> dict[str, Any]:
    """Approved set manifest: content plus the exact confirmed recipient set."""
    payload = _payload(session, version, contact_ids)
    payload["manifest_sha256"] = canonical_sha256(payload)
    return payload


def build_recipient_manifest(
    session: Session,
    version: ReportVersion,
    contact_id: str,
    *,
    approved_recipients_sha256: str,
) -> dict[str, Any]:
    """Per-recipient manifest derived from the approved set manifest.

    It keeps the approved content and this recipient's own entry, and records the hash of the
    confirmed recipient set so an individual event cannot be compared against a different scope.
    """
    payload = _payload(session, version, [contact_id])
    payload["approved_recipients_sha256"] = approved_recipients_sha256
    payload["manifest_sha256"] = canonical_sha256(payload)
    return payload


def manifest_json(manifest: dict[str, Any]) -> str:
    return canonical_json(manifest)
