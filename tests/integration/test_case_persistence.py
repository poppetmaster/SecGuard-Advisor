"""Persistencia de un caso después de reiniciar el motor de base de datos."""

from pathlib import Path

from sqlalchemy import select

from secguard_advisor.cases.schemas import CaseInput
from secguard_advisor.cases.service import create_case
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import Asset, Case


def test_case_survives_engine_restart(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'persist.sqlite3'}"

    engine = create_engine_for_url(url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        case = create_case(
            session,
            CaseInput.from_form(
                title="Caso persistente",
                description="Contexto que debe sobrevivir",
                assets="api-gateway\nportal",
            ),
        )
        session.commit()
        case_id = case.id
    engine.dispose()

    engine = create_engine_for_url(url)
    factory = create_session_factory(engine)
    with factory() as session:
        stored = session.get(Case, case_id)
        assert stored is not None
        assert stored.title == "Caso persistente"
        assert stored.description == "Contexto que debe sobrevivir"
        assert stored.context_is_synthetic is True
        assert stored.ai_application is None
        assets = list(
            session.scalars(
                select(Asset).where(Asset.case_id == case_id).order_by(Asset.name.asc())
            )
        )
        assert [asset.name for asset in assets] == ["api-gateway", "portal"]
    engine.dispose()
