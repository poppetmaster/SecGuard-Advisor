"""Taxonomía de errores y mensajes para el usuario."""

from dataclasses import dataclass

from fastapi.responses import JSONResponse


@dataclass(frozen=True, slots=True)
class ErrorSpec:
    code: str
    status: int
    message: str


ERRORS: dict[str, ErrorSpec] = {
    "not_found": ErrorSpec("not_found", 404, "No encontrado en este caso."),
    "forbidden_origin": ErrorSpec(
        "forbidden_origin", 403, "La solicitud no proviene de esta aplicación."
    ),
    "validation_error": ErrorSpec("validation_error", 422, "Revisá los datos ingresados."),
    "conflict": ErrorSpec("conflict", 409, "La operación entra en conflicto con el estado actual."),
    "busy": ErrorSpec("busy", 429, "El sistema está ocupado; intentá de nuevo."),
    "payload_too_large": ErrorSpec(
        "payload_too_large", 413, "El archivo supera el tamaño permitido."
    ),
    "unsupported_media_type": ErrorSpec(
        "unsupported_media_type", 415, "El tipo de archivo no está permitido."
    ),
    "model_unavailable": ErrorSpec("model_unavailable", 503, "El modelo local no responde."),
    "timeout": ErrorSpec("timeout", 504, "La consulta excedió el tiempo de espera."),
    "run_timeout": ErrorSpec(
        "run_timeout", 504, "La consulta excedió el tiempo de espera del turno."
    ),
    "context_budget_exceeded": ErrorSpec(
        "context_budget_exceeded",
        500,
        "La consulta excede el presupuesto de contexto del modelo.",
    ),
    "invalid_model_output": ErrorSpec(
        "invalid_model_output",
        500,
        "El modelo devolvió una respuesta que no se pudo interpretar.",
    ),
    "internal_error": ErrorSpec("internal_error", 500, "Ocurrió un error interno."),
}


class AppError(Exception):
    """Error de aplicación con código y estado HTTP."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.spec = ERRORS.get(code, ERRORS["internal_error"])
        self.message = message or self.spec.message
        super().__init__(self.message)

    @property
    def code(self) -> str:
        return self.spec.code

    @property
    def status(self) -> int:
        return self.spec.status


def message_for(code: str) -> str:
    """Devuelve el mensaje en español de un código."""
    return ERRORS.get(code, ERRORS["internal_error"]).message


def error_response(code: str, detail: str | None = None) -> JSONResponse:
    """Construye una respuesta JSON uniforme."""
    spec = ERRORS.get(code, ERRORS["internal_error"])
    return JSONResponse(
        status_code=spec.status,
        content={
            "error": {
                "code": spec.code,
                "message": detail or spec.message,
            }
        },
    )
