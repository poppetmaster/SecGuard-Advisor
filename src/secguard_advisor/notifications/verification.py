"""Contact verification challenges with hashed one-time codes."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from secguard_advisor.db.models import ContactChannel, ContactVerificationChallenge, utc_now_iso
from secguard_advisor.notifications.channels.base import TelegramError, TelegramTransport
from secguard_advisor.notifications.contacts import get_contact
from secguard_advisor.notifications.errors import NotificationError

CHALLENGE_TTL = timedelta(minutes=10)
REQUEST_WINDOW = timedelta(minutes=10)
MAX_REQUESTS = 3
MAX_ATTEMPTS = 3


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def _pending_challenge(session: Session, contact_id: str) -> ContactVerificationChallenge | None:
    return session.scalar(
        select(ContactVerificationChallenge)
        .where(
            ContactVerificationChallenge.contact_id == contact_id,
            ContactVerificationChallenge.status == "pending",
        )
        .order_by(ContactVerificationChallenge.created_at.desc())
    )


def start_verification(
    session: Session,
    *,
    contact_id: str,
    transport: TelegramTransport,
) -> ContactVerificationChallenge:
    """Send a code; this technical send is independent from report eligibility.

    The request is counted and persisted before the network call, and no write transaction stays
    open while the transport runs.
    """
    contact = get_contact(session, contact_id)
    chat_id = contact.chat_id
    chat_type = contact.chat_type
    now = datetime.now(UTC)
    window_start = now - REQUEST_WINDOW
    recent = (
        session.scalar(
            select(func.count())
            .select_from(ContactVerificationChallenge)
            .where(
                ContactVerificationChallenge.contact_id == contact_id,
                ContactVerificationChallenge.created_at >= window_start.isoformat(),
            )
        )
        or 0
    )
    if recent >= MAX_REQUESTS:
        raise NotificationError("rate_limited", "Se superó el límite de solicitudes de código.")
    session.commit()

    bot = transport.get_me()
    chat = transport.get_chat(chat_id)
    if chat_type in {"group", "supergroup", "channel"}:
        transport.get_chat_member(chat_id, bot.bot_id)

    previous = _pending_challenge(session, contact_id)
    if previous is not None:
        previous.status = "locked"

    contact.chat_type = chat.chat_type
    contact.display_name = chat.title or contact.display_name
    contact.chat_fingerprint = hashlib.sha256(f"{bot.bot_id}:{chat_id}".encode()).hexdigest()

    code = f"{secrets.randbelow(1_000_000):06d}"
    challenge = ContactVerificationChallenge(
        contact_id=contact.id,
        bot_fingerprint=contact.chat_fingerprint,
        code_sha256=_hash_code(code),
        purpose="contact_verification",
        status="pending",
        created_at=now.isoformat(),
        expires_at=(now + CHALLENGE_TTL).isoformat(),
        attempts=0,
        max_attempts=MAX_ATTEMPTS,
        last_sent_at=now.isoformat(),
        request_count=1,
        window_started_at=window_start.isoformat(),
    )
    session.add(challenge)
    session.commit()

    try:
        transport.send_message(
            chat_id,
            "Código de verificación de SecGuard Advisor: "
            f"{code}. Vence en 10 minutos. No lo compartas.",
        )
    except TelegramError as exc:
        challenge.status = "locked"
        session.commit()
        raise NotificationError("verification_send_failed", str(exc), persist_state=True) from exc
    return challenge


def confirm_verification(
    session: Session,
    *,
    contact_id: str,
    code: str,
    verified_by: str,
) -> ContactChannel:
    contact = get_contact(session, contact_id)
    challenge = _pending_challenge(session, contact_id)
    if challenge is None:
        raise NotificationError("code_consumed", "No hay un desafío pendiente.")
    now = datetime.now(UTC)
    if datetime.fromisoformat(challenge.expires_at) <= now:
        challenge.status = "expired"
        session.flush()
        raise NotificationError("code_expired", "El código expiró.", persist_state=True)
    if challenge.attempts >= challenge.max_attempts:
        challenge.status = "locked"
        session.flush()
        raise NotificationError(
            "verification_locked", "El desafío está bloqueado.", persist_state=True
        )
    challenge.attempts += 1
    if _hash_code((code or "").strip()) != challenge.code_sha256:
        if challenge.attempts >= challenge.max_attempts:
            challenge.status = "locked"
        session.flush()
        raise NotificationError("code_invalid", "El código no es correcto.", persist_state=True)
    challenge.status = "consumed"
    challenge.consumed_at = now.isoformat()
    contact.status = "verified"
    contact.verified_at = now.isoformat()
    contact.verified_by = (verified_by or "").strip() or "Responsable no declarado"
    contact.verification_method = "getchat_code_v1"
    contact.verification_evidence = (
        f"getchat_code_v1; bot_fingerprint={challenge.bot_fingerprint}; "
        f"code_sha256={challenge.code_sha256}"
    )
    if contact.chat_fingerprint is None:
        contact.chat_fingerprint = challenge.bot_fingerprint
    contact.updated_at = utc_now_iso()
    session.flush()
    return contact


def expire_pending(session: Session, contact_id: str) -> int:
    now = datetime.now(UTC).isoformat()
    rows = list(
        session.scalars(
            select(ContactVerificationChallenge).where(
                ContactVerificationChallenge.contact_id == contact_id,
                ContactVerificationChallenge.status == "pending",
                ContactVerificationChallenge.expires_at <= now,
            )
        )
    )
    for row in rows:
        row.status = "expired"
    session.flush()
    return len(rows)
