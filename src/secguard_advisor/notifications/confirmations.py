"""Human confirmation of the exact report manifest."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from secguard_advisor.db.models import ReportConfirmation, ReportVersion, utc_now_iso
from secguard_advisor.notifications.contacts import get_contact, is_eligible
from secguard_advisor.notifications.errors import NotificationError
from secguard_advisor.notifications.manifest import build_manifest
from secguard_advisor.reports.canonical import canonical_json, parse_json
from secguard_advisor.reports.service import get_version


def invalidate_for_version(session: Session, version_id: str) -> int:
    rows = list(
        session.scalars(
            select(ReportConfirmation).where(
                ReportConfirmation.report_version_id == version_id,
                ReportConfirmation.invalidated_at.is_(None),
            )
        )
    )
    now = utc_now_iso()
    for row in rows:
        row.invalidated_at = now
    session.flush()
    return len(rows)


def create_confirmation(
    session: Session,
    *,
    case_id: str,
    report_id: str,
    version_number: int,
    contact_ids: list[str],
    created_by: str,
) -> ReportConfirmation:
    if not contact_ids:
        raise NotificationError("recipient_required", "Seleccioná al menos un destinatario.")
    version = get_version(session, case_id, report_id, version_number)
    if version.status != "ready":
        raise NotificationError("version_not_ready", "La versión no está lista.")
    contacts = [get_contact(session, contact_id) for contact_id in dict.fromkeys(contact_ids)]
    for contact in contacts:
        if not is_eligible(session, contact=contact, case_id=case_id):
            raise NotificationError(
                "contact_not_eligible",
                "Un contacto no está verificado, activo, consentido o vinculado al caso.",
            )
    manifest = build_manifest(session, version, [contact.id for contact in contacts])
    invalidate_for_version(session, version.id)
    confirmation = ReportConfirmation(
        case_id=case_id,
        report_version_id=version.id,
        manifest_json=canonical_json(manifest),
        manifest_sha256=manifest["manifest_sha256"],
        contacts_json=canonical_json([contact.id for contact in contacts]),
        created_by=(created_by or "").strip() or "Responsable no declarado",
    )
    session.add(confirmation)
    session.flush()
    return confirmation


def get_confirmation(session: Session, case_id: str, confirmation_id: str) -> ReportConfirmation:
    confirmation = session.scalar(
        select(ReportConfirmation).where(
            ReportConfirmation.id == confirmation_id,
            ReportConfirmation.case_id == case_id,
        )
    )
    if confirmation is None:
        raise NotificationError("confirmation_not_found", "La confirmación no existe.")
    return confirmation


def validate_confirmation(
    session: Session, confirmation: ReportConfirmation
) -> tuple[ReportVersion, dict[str, Any], list[str]]:
    if confirmation.invalidated_at is not None:
        raise NotificationError("confirmation_invalid", "La confirmación fue invalidada.")
    version = session.get(ReportVersion, confirmation.report_version_id)
    if version is None or version.status != "ready":
        raise NotificationError("version_not_found", "La versión confirmada no está disponible.")
    contact_ids = list(parse_json(confirmation.contacts_json))
    manifest = build_manifest(session, version, contact_ids)
    if manifest["manifest_sha256"] != confirmation.manifest_sha256:
        confirmation.invalidated_at = utc_now_iso()
        session.flush()
        raise NotificationError(
            "manifest_mismatch", "El contenido o los destinatarios cambiaron; confirmá de nuevo."
        )
    return version, manifest, contact_ids
