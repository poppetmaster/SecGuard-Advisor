"""Contacts, consent and case authorization for Telegram."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from secguard_advisor.db.models import Case, ContactCaseLink, ContactChannel, utc_now_iso
from secguard_advisor.notifications.errors import NotificationError

CHAT_ID_PATTERN = re.compile(r"^-?\d{3,64}$")
CONTACT_STATUSES = ("unverified", "verified", "revoked", "disabled")
CONSENT_STATUSES = ("pending", "granted", "revoked")


def chat_fingerprint(bot_id: str, chat_id: str) -> str:
    return hashlib.sha256(f"{bot_id}:{chat_id}".encode()).hexdigest()


def mask_chat_id(chat_id: str) -> str:
    digits = "".join(char for char in chat_id if char.isdigit())
    if len(digits) <= 4:
        return "••••"
    return f"••••{digits[-4:]}"


def normalize_chat_id(value: str) -> str:
    chat_id = (value or "").strip()
    if not CHAT_ID_PATTERN.fullmatch(chat_id):
        raise NotificationError("invalid_chat_id", "El identificador de chat no es válido.")
    return chat_id


def create_contact(
    session: Session,
    *,
    alias: str,
    chat_id: str,
    chat_type: str = "private",
    display_name: str | None = None,
) -> ContactChannel:
    clean_alias = (alias or "").strip()
    if not clean_alias:
        raise NotificationError("invalid_alias", "El alias es obligatorio.")
    clean_chat = normalize_chat_id(chat_id)
    if chat_type not in {"private", "group", "supergroup", "channel"}:
        raise NotificationError("invalid_chat_type", "El tipo de chat no es válido.")
    if session.scalar(
        select(ContactChannel).where(
            ContactChannel.channel == "telegram", ContactChannel.chat_id == clean_chat
        )
    ):
        raise NotificationError("duplicate_contact", "Ese destino ya está registrado.")
    contact = ContactChannel(
        alias=clean_alias,
        channel="telegram",
        chat_id=clean_chat,
        chat_type=chat_type,
        display_name=(display_name or "").strip() or None,
        status="unverified",
        consent_status="pending",
        active=False,
    )
    session.add(contact)
    session.flush()
    return contact


def list_contacts(session: Session) -> list[ContactChannel]:
    return list(session.scalars(select(ContactChannel).order_by(ContactChannel.alias)))


def get_contact(session: Session, contact_id: str) -> ContactChannel:
    contact = session.get(ContactChannel, contact_id)
    if contact is None:
        raise NotificationError("contact_not_found", "El contacto no existe.")
    return contact


def set_contact_status(session: Session, contact_id: str, status: str) -> ContactChannel:
    if status not in CONTACT_STATUSES:
        raise NotificationError("invalid_contact_status", "El estado del contacto no es válido.")
    contact = get_contact(session, contact_id)
    if status == "verified" and contact.verified_at is None:
        raise NotificationError(
            "contact_unverified", "La verificación solo la registra el desafío."
        )
    contact.status = status
    if status in {"revoked", "disabled"}:
        contact.active = False
    contact.updated_at = utc_now_iso()
    session.flush()
    return contact


def set_consent(
    session: Session, contact_id: str, status: str, *, declared_by: str
) -> ContactChannel:
    if status not in CONSENT_STATUSES:
        raise NotificationError("invalid_consent", "El consentimiento no es válido.")
    contact = get_contact(session, contact_id)
    contact.consent_status = status
    contact.consent_at = utc_now_iso() if status == "granted" else None
    if status == "revoked":
        contact.active = False
    contact.updated_at = utc_now_iso()
    session.flush()
    return contact


def set_active(session: Session, contact_id: str, active: bool) -> ContactChannel:
    contact = get_contact(session, contact_id)
    if active and contact.status != "verified":
        raise NotificationError("contact_unverified", "No se activa un contacto sin verificar.")
    if active and contact.consent_status != "granted":
        raise NotificationError("consent_missing", "No se activa un contacto sin consentimiento.")
    contact.active = active
    contact.updated_at = utc_now_iso()
    session.flush()
    return contact


def authorize_case(
    session: Session, *, contact_id: str, case_id: str, authorized: bool
) -> ContactCaseLink:
    get_contact(session, contact_id)
    if session.get(Case, case_id) is None:
        raise NotificationError("case_not_found", "El caso no existe.")
    link = session.get(ContactCaseLink, (contact_id, case_id))
    if link is None:
        link = ContactCaseLink(contact_id=contact_id, case_id=case_id, authorized=authorized)
        session.add(link)
    else:
        link.authorized = authorized
    session.flush()
    return link


def case_link(session: Session, contact_id: str, case_id: str) -> ContactCaseLink | None:
    return session.get(ContactCaseLink, (contact_id, case_id))


def is_eligible(session: Session, *, contact: ContactChannel, case_id: str) -> bool:
    link = case_link(session, contact.id, case_id)
    return bool(
        contact.status == "verified"
        and contact.active
        and contact.consent_status == "granted"
        and link is not None
        and link.authorized
    )


def eligible_contacts(session: Session, case_id: str) -> list[ContactChannel]:
    return [
        contact
        for contact in list_contacts(session)
        if is_eligible(session, contact=contact, case_id=case_id)
    ]


@dataclass(frozen=True, slots=True)
class ContactView:
    id: str
    alias: str
    chat_type: str
    masked_chat: str
    status: str
    consent_status: str
    active: bool
    verified_at: str | None
    verified_by: str | None
    cases: tuple[str, ...]
