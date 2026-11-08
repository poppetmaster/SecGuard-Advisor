"""Alcance de caso resuelto por la aplicación."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from secguard_advisor.db.models import Case


class CaseNotFoundError(LookupError):
    """El caso no existe en el almacenamiento."""


@dataclass(frozen=True, slots=True)
class CaseScope:
    """Alcance autorizado de una operación."""

    case_id: str


def resolve_case_scope(session: Session, case_id: str) -> CaseScope:
    """Resuelve y valida el alcance a partir de la ruta."""
    if not case_id or session.get(Case, case_id) is None:
        raise CaseNotFoundError(case_id)
    return CaseScope(case_id=case_id)


def require_case(session: Session, scope: CaseScope) -> Case:
    """Devuelve el caso del alcance o falla si no existe."""
    case = session.get(Case, scope.case_id)
    if case is None:
        raise CaseNotFoundError(scope.case_id)
    return case
