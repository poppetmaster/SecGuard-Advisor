"""Servicio de gestión de casos."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from secguard_advisor.cases.schemas import CaseInput
from secguard_advisor.cases.scope import CaseScope, require_case
from secguard_advisor.db.models import Asset, Case

CASE_SYNTHETIC_NOTICE = "Escenario educativo sintético. No corresponde a una empresa real."


def create_case(session: Session, data: CaseInput) -> Case:
    """Crea el caso y sus activos sin confirmar la transacción."""
    case = Case(
        title=data.title,
        description=data.description,
        ai_application=data.ai_application,
        data_processed=data.data_processed,
        restrictions=data.restrictions,
        context_is_synthetic=True,
        synthetic_notice=CASE_SYNTHETIC_NOTICE,
    )
    session.add(case)
    session.flush()

    for name in data.assets:
        session.add(Asset(case_id=case.id, name=name))
    session.flush()

    return case


def list_cases(session: Session) -> list[Case]:
    """Lista los casos del más reciente al más antiguo."""
    return list(session.scalars(select(Case).order_by(Case.created_at.desc(), Case.title.asc())))


def get_case(session: Session, scope: CaseScope) -> Case:
    """Devuelve el caso del alcance autorizado."""
    return require_case(session, scope)


def list_assets(session: Session, case_id: str) -> list[Asset]:
    """Lista los activos de un caso por nombre."""
    return list(
        session.scalars(select(Asset).where(Asset.case_id == case_id).order_by(Asset.name.asc()))
    )


def display_value(value: str | None) -> str:
    """Representa un campo vacío como desconocido."""
    if value is None or not value.strip():
        return "Desconocido"
    return value
