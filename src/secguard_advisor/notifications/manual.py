"""Manual confirmation and delivery orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from secguard_advisor.config import Settings
from secguard_advisor.db.models import ContactChannel, ReportVersion
from secguard_advisor.notifications.channels.base import TelegramTransport
from secguard_advisor.notifications.confirmations import get_confirmation, validate_confirmation
from secguard_advisor.notifications.contacts import eligible_contacts, is_eligible
from secguard_advisor.notifications.delivery import ensure_event, list_events
from secguard_advisor.notifications.errors import NotificationError
from secguard_advisor.notifications.executor import execute_event
from secguard_advisor.notifications.manifest import build_manifest

EXECUTABLE = ("prepared", "queued")


@dataclass(frozen=True, slots=True)
class ManualPreview:
    version: ReportVersion
    contacts: list[ContactChannel]
    manifest: dict[str, Any]


def preview_manual(
    session: Session,
    *,
    case_id: str,
    report_id: str,
    version_number: int,
    contact_ids: list[str] | None = None,
) -> ManualPreview:
    from secguard_advisor.reports.service import get_version

    version = get_version(session, case_id, report_id, version_number)
    contacts = eligible_contacts(session, case_id)
    selected = (
        [contact for contact in contacts if contact.id in set(contact_ids)]
        if contact_ids
        else contacts
    )
    for contact in selected:
        if not is_eligible(session, contact=contact, case_id=case_id):
            raise NotificationError("contact_not_eligible", "Un contacto no es elegible.")
    manifest = build_manifest(session, version, [contact.id for contact in selected])
    return ManualPreview(version, selected, manifest)


def send_manual(
    factory: sessionmaker[Session],
    settings: Settings,
    transport: TelegramTransport,
    *,
    case_id: str,
    confirmation_id: str,
) -> list[str]:
    """Create or reuse one event per confirmed recipient, then execute only executable ones.

    A recipient that lost eligibility after the confirmation is not allowed to block the others:
    the executor skips only that recipient with a safe error code.
    """
    plan: list[tuple[str, str]] = []
    with factory() as session:
        confirmation = get_confirmation(session, case_id, confirmation_id)
        version, manifest, contact_ids = validate_confirmation(session, confirmation)
        for contact_id in contact_ids:
            contact = session.get(ContactChannel, contact_id)
            if contact is None:
                continue
            event, _created = ensure_event(
                session,
                version=version,
                contact=contact,
                manifest=manifest,
                mode="manual",
                confirmed_by=confirmation.created_by,
                confirmed_at=confirmation.created_at,
                confirmation_id=confirmation.id,
            )
            plan.append((event.id, event.status))
        session.commit()
    for event_id, status in plan:
        if status in EXECUTABLE:
            execute_event(factory, settings, transport, event_id)
    planned = {event_id for event_id, _status in plan}
    with factory() as session:
        return [event.id for event in list_events(session, case_id) if event.id in planned]


def retry_manual(
    factory: sessionmaker[Session],
    settings: Settings,
    transport: TelegramTransport,
    *,
    case_id: str,
    event_id: str,
) -> str:
    from secguard_advisor.notifications.executor import retry_event

    return retry_event(factory, settings, transport, event_id)
