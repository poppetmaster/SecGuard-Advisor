"""Errores y códigos seguros reservados para notificaciones (Corte B)."""

from __future__ import annotations

NOTIFICATION_ERROR_CODES = {
    "contact_unverified": "El contacto no está verificado.",
    "consent_missing": "El contacto no tiene consentimiento vigente.",
    "case_not_authorized": "El contacto no está autorizado para este caso.",
    "manifest_mismatch": "El contenido aprobado no coincide con los artefactos.",
    "rule_inactive": "La regla no está activa o su versión no es vigente.",
    "verification_locked": "El desafío de verificación está bloqueado.",
    "verification_send_failed": "No se pudo enviar el código de verificación.",
    "code_invalid": "El código de verificación es incorrecto.",
    "code_expired": "El código de verificación expiró.",
    "code_consumed": "El código de verificación ya fue consumido.",
    "rate_limited": "Se superó el límite de solicitudes.",
    "timeout": "La operación no respondió a tiempo.",
    "interrupted": "La operación se interrumpió y requiere revisión.",
    "document_render_failed": "No se pudo generar el documento.",
    "pdf_integrity_mismatch": "El PDF no coincide con el aprobado; no se envía.",
    "uncertain_requires_review": "Un resultado incierto exige revisión explícita.",
    "retry_not_allowed": "El evento no admite reintento manual.",
    "component_revalidation_failed": "El destinatario o el contenido dejó de ser válido.",
}


class NotificationError(ValueError):
    """Error de dominio de notificaciones con código seguro.

    ``persist_state`` marca los fallos cuyo estado de seguridad (intentos, bloqueo, expiración)
    debe confirmarse aunque la respuesta HTTP sea un error.
    """

    def __init__(
        self, code: str, message: str | None = None, *, persist_state: bool = False
    ) -> None:
        self.code = code
        self.message = message or NOTIFICATION_ERROR_CODES.get(code, "Error de notificación.")
        self.persist_state = persist_state
        super().__init__(self.message)
