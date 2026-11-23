"""Errores y códigos seguros reservados para notificaciones (Corte B)."""

from __future__ import annotations

NOTIFICATION_ERROR_CODES = {
    "contact_unverified": "El contacto no está verificado.",
    "consent_missing": "El contacto no tiene consentimiento vigente.",
    "case_not_authorized": "El contacto no está autorizado para este caso.",
    "manifest_mismatch": "El contenido aprobado no coincide con los artefactos.",
    "rule_inactive": "La regla no está activa o su versión no es vigente.",
    "verification_locked": "El desafío de verificación está bloqueado.",
    "code_invalid": "El código de verificación es incorrecto.",
    "code_expired": "El código de verificación expiró.",
    "code_consumed": "El código de verificación ya fue consumido.",
    "rate_limited": "Se superó el límite de solicitudes.",
    "timeout": "La operación no respondió a tiempo.",
    "interrupted": "La operación se interrumpió y requiere revisión.",
    "document_render_failed": "No se pudo generar el documento.",
}


class NotificationError(ValueError):
    """Error de dominio de notificaciones con código seguro."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        self.message = message or NOTIFICATION_ERROR_CODES.get(code, "Error de notificación.")
        super().__init__(self.message)
