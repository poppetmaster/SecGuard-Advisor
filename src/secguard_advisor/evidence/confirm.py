"""Confirmación por API de lectura de una traza observada (T091).

Este módulo es el único que escribe `trace_status=confirmed`. La aplicación
normal nunca lo hace. La confirmación exige que la traza exista, pertenezca al
proyecto configurado y esté correlacionada con la ejecución local por
`run_id`, `case_id` e intento.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from secguard_advisor.config import Settings
from secguard_advisor.db.models import Run, utc_now_iso

_TRACE_SOURCES = {"submitted", "confirmed"}


class ConfirmationError(RuntimeError):
    """La traza no puede confirmarse; el estado local no se modifica."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class ConfirmationResult:
    status: str
    run_id: str
    trace_id: str
    project: str
    reviewer: str
    confirmed_at: str
    trace_name: str
    trace_started_at: str | None
    trace_url: str | None


def _default_client(*, api_url: str, api_key: str, timeout_ms: int):
    from langsmith import Client

    return Client(api_url=api_url, api_key=api_key, timeout_ms=timeout_ms)


def confirm_trace(
    factory: sessionmaker[Session],
    settings: Settings,
    *,
    run_id: str,
    trace_id: str,
    reviewer: str,
    client_factory=None,
) -> ConfirmationResult:
    """Verifica la traza en LangSmith y solo entonces marca `confirmed`."""
    reviewer = (reviewer or "").strip()
    if not reviewer:
        raise ConfirmationError(
            "reviewer_required",
            "Se requiere la identidad declarada de quien confirma la traza.",
        )
    trace_id = (trace_id or "").strip()
    if not trace_id:
        raise ConfirmationError("trace_id_required", "Falta el identificador de traza.")

    with factory() as session:
        run = session.get(Run, run_id)
        if run is None:
            raise ConfirmationError("run_not_found", "La ejecución local no existe.")
        if run.trace_status == "confirmed":
            if run.trace_id == trace_id and run.trace_confirmed_by:
                return ConfirmationResult(
                    status="already_confirmed",
                    run_id=run.id,
                    trace_id=trace_id,
                    project=settings.langsmith_project,
                    reviewer=run.trace_confirmed_by,
                    confirmed_at=run.trace_confirmed_at or "",
                    trace_name="",
                    trace_started_at=None,
                    trace_url=run.trace_url,
                )
            raise ConfirmationError(
                "already_confirmed_different_trace",
                "La ejecución ya está confirmada con otra traza.",
            )
        if run.trace_status not in _TRACE_SOURCES:
            raise ConfirmationError(
                "trace_not_submitted",
                "La ejecución no tiene una traza enviada que pueda confirmarse.",
            )
        if run.trace_id is not None and run.trace_id != trace_id:
            raise ConfirmationError(
                "trace_mismatch",
                "El identificador de traza no coincide con el registrado localmente.",
            )
        case_id = run.case_id
        attempt_no = run.attempt_no

    api_key = settings.langsmith_api_key
    if api_key is None:
        raise ConfirmationError(
            "credentials_missing",
            "No hay credenciales de LangSmith para verificar la traza.",
        )

    client_factory = client_factory or _default_client
    try:
        client = client_factory(
            api_url=settings.langsmith_endpoint,
            api_key=api_key.get_secret_value(),
            timeout_ms=5000,
        )
        remote = client.read_run(trace_id)
        project = client.read_project(project_name=settings.langsmith_project)
    except Exception as exc:
        raise ConfirmationError(
            "api_unavailable",
            "No se pudo verificar la traza en LangSmith.",
        ) from exc

    if remote is None or str(getattr(remote, "id", "")) != trace_id:
        raise ConfirmationError("trace_not_found", "La traza no existe en LangSmith.")
    if project is None or str(getattr(remote, "session_id", "")) != str(getattr(project, "id", "")):
        raise ConfirmationError(
            "project_mismatch",
            "La traza no pertenece al proyecto configurado.",
        )

    inputs = getattr(remote, "inputs", None) or {}
    if inputs.get("run_id") != run_id:
        raise ConfirmationError(
            "trace_not_linked",
            "La traza existe pero no corresponde a esta ejecución local.",
        )
    if inputs.get("case_id") != case_id or inputs.get("attempt_no") != attempt_no:
        raise ConfirmationError(
            "trace_not_linked",
            "Los metadatos de la traza no coinciden con la ejecución local.",
        )

    confirmed_at = utc_now_iso()
    trace_url = None
    try:
        trace_url = client._construct_run_url(
            run=remote,
            project_name=settings.langsmith_project,
            project_id=getattr(project, "id", None),
        )
    except Exception:
        trace_url = None

    evidence = {
        "run_id": run_id,
        "trace_id": trace_id,
        "project": settings.langsmith_project,
        "trace_name": getattr(remote, "name", None),
        "trace_started_at": (
            getattr(remote, "start_time", None).isoformat()
            if getattr(remote, "start_time", None) is not None
            else None
        ),
        "trace_inputs": {
            "run_id": inputs.get("run_id"),
            "case_id": inputs.get("case_id"),
            "attempt_no": inputs.get("attempt_no"),
            "prompt_version": inputs.get("prompt_version"),
        },
    }
    with factory() as session:
        run = session.get(Run, run_id)
        if run is None:
            raise ConfirmationError("run_not_found", "La ejecución local no existe.")
        run.trace_status = "confirmed"
        run.trace_id = trace_id
        if trace_url:
            run.trace_url = trace_url
        run.trace_confirmed_by = reviewer
        run.trace_confirmed_at = confirmed_at
        run.trace_evidence_json = json.dumps(evidence, ensure_ascii=False, sort_keys=True)
        session.commit()
        return ConfirmationResult(
            status="confirmed",
            run_id=run_id,
            trace_id=trace_id,
            project=settings.langsmith_project,
            reviewer=reviewer,
            confirmed_at=confirmed_at,
            trace_name=getattr(remote, "name", ""),
            trace_started_at=evidence["trace_started_at"],
            trace_url=run.trace_url,
        )
