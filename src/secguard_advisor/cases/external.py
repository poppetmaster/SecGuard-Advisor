"""Autorización explícita por caso para procesamiento externo (005)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from secguard_advisor.db.models import ExternalProcessingAuthorization

ExternalScope = Literal["public_corpus", "fictional_case"]
POLICY_VERSION = "005-external-v1"
ALLOWED_SCOPES: tuple[str, ...] = ("public_corpus", "fictional_case")


class ExternalProcessingBlocked(RuntimeError):
    """El caso no tiene autorización externa vigente."""

    code = "external_processing_blocked"


class ExternalToolBlocked(RuntimeError):
    """La herramienta no está permitida con el proveedor externo."""

    code = "external_tool_blocked"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def authorize_case(
    session: Session,
    *,
    case_id: str,
    scope: str,
    authorized_by: str,
    note: str | None = None,
) -> ExternalProcessingAuthorization:
    """Otorga autorización y revoca la anterior vigente del mismo caso."""
    if scope not in ALLOWED_SCOPES:
        raise ValueError("El alcance externo debe ser public_corpus o fictional_case.")
    identity = (authorized_by or "").strip()
    if not identity:
        raise ValueError("La autorización externa requiere una identidad declarada.")
    revoke_case(session, case_id=case_id)
    authorization = ExternalProcessingAuthorization(
        case_id=case_id,
        scope=scope,
        policy_version=POLICY_VERSION,
        authorized_by=identity,
        authorized_at=_now(),
        note=(note or "").strip() or None,
    )
    session.add(authorization)
    session.flush()
    return authorization


def revoke_case(session: Session, *, case_id: str) -> int:
    """Revoca todas las autorizaciones vigentes del caso."""
    rows = list(
        session.scalars(
            select(ExternalProcessingAuthorization).where(
                ExternalProcessingAuthorization.case_id == case_id,
                ExternalProcessingAuthorization.revoked_at.is_(None),
            )
        )
    )
    now = _now()
    for row in rows:
        row.revoked_at = now
    return len(rows)


def active_authorization(
    session: Session, *, case_id: str
) -> ExternalProcessingAuthorization | None:
    return session.scalar(
        select(ExternalProcessingAuthorization)
        .where(
            ExternalProcessingAuthorization.case_id == case_id,
            ExternalProcessingAuthorization.revoked_at.is_(None),
        )
        .order_by(ExternalProcessingAuthorization.authorized_at.desc())
    )


def ensure_external_allowed(
    session: Session, *, case_id: str, provider: str
) -> ExternalProcessingAuthorization | None:
    """Compuerta previa a cualquier envío o conteo externo."""
    if provider == "ollama":
        return None
    authorization = active_authorization(session, case_id=case_id)
    if authorization is None:
        raise ExternalProcessingBlocked(
            "El caso no tiene autorización vigente para procesamiento externo. "
            "Usá Ollama o registrá una autorización local para corpus público o caso ficticio."
        )
    return authorization
