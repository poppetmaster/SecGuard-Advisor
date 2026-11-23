"""Errores y códigos estables del informe ejecutivo."""

from __future__ import annotations


class ReportError(ValueError):
    """Error de dominio del informe con código seguro."""

    def __init__(self, code: str, message: str, status: int = 422) -> None:
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


REPORT_ERROR_CODES = {
    "snapshot_not_found": "La instantánea no existe o no está confirmada en este caso.",
    "snapshot_not_confirmed": "Solo una importación confirmada puede generar un informe.",
    "report_not_found": "El informe no existe en este caso.",
    "version_not_found": "La versión del informe no existe.",
    "pdf_not_ready": "El PDF de esta versión no está disponible.",
    "artifact_write_failed": "No se pudo guardar un artefacto del informe.",
    "pdf_render_failed": "No se pudo generar el PDF del informe.",
    "charts_render_failed": "No se pudieron generar las gráficas del PDF.",
    "synthesis_invalid": "La síntesis no cumple el contrato del informe.",
    "generation_key_conflict": "La clave de generación ya está asociada a otra versión.",
}


def report_error(code: str) -> ReportError:
    return ReportError(code, REPORT_ERROR_CODES[code])
