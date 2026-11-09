"""Pruebas del servicio de casos de US1."""

from pathlib import Path

import pytest

from secguard_advisor.cases.schemas import (
    MAX_ASSET_NAME,
    MAX_TITLE,
    CaseInput,
    CaseValidationError,
)
from secguard_advisor.cases.scope import CaseNotFoundError, resolve_case_scope
from secguard_advisor.cases.service import (
    case_context,
    create_case,
    display_value,
    get_case,
    list_assets,
    list_cases,
)
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory


@pytest.fixture
def session(tmp_path: Path):
    engine = create_engine_for_url(f"sqlite:///{tmp_path / 'cases.sqlite3'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as db_session:
        yield db_session
    engine.dispose()


def test_title_is_required() -> None:
    with pytest.raises(CaseValidationError) as captured:
        CaseInput.from_form(title="   ")

    assert "title" in captured.value.errors


def test_title_length_is_limited() -> None:
    with pytest.raises(CaseValidationError) as captured:
        CaseInput.from_form(title="x" * (MAX_TITLE + 1))

    assert "title" in captured.value.errors


def test_optional_fields_are_unknown() -> None:
    data = CaseInput.from_form(title="  Caso educativo  ")

    assert data.title == "Caso educativo"
    assert data.description is None
    assert data.ai_application is None
    assert data.data_processed is None
    assert data.restrictions is None
    assert data.assets == ()


def test_assets_are_parsed_and_deduplicated() -> None:
    data = CaseInput.from_form(title="Caso", assets="api-gateway\n\napi-gateway\nportal\n")

    assert data.assets == ("api-gateway", "portal")


def test_asset_name_length_is_limited() -> None:
    with pytest.raises(CaseValidationError) as captured:
        CaseInput.from_form(title="Caso", assets="x" * (MAX_ASSET_NAME + 1))

    assert "assets" in captured.value.errors


def test_create_case_persists_context_and_assets(session) -> None:
    data = CaseInput.from_form(
        title="Evaluación de un asistente",
        description="Contexto educativo",
        ai_application="Asistente interno",
        data_processed="Documentos públicos",
        restrictions="Sin datos reales",
        assets="api-gateway\nportal",
    )

    case = create_case(session, data)
    session.commit()

    assert case.id
    assert case.context_is_synthetic is True
    assert case.synthetic_notice
    assert case.description == "Contexto educativo"
    assert [asset.name for asset in list_assets(session, case.id)] == [
        "api-gateway",
        "portal",
    ]


def test_general_case_without_ai_application(session) -> None:
    data = CaseInput.from_form(
        title="Análisis de ciberseguridad empresarial",
        description="Revisión del acceso remoto y la gestión de vulnerabilidades.",
        ai_application="Infraestructura tecnológica y acceso remoto",
        data_processed="",
        restrictions="",
        assets="vpn\nservidor-de-gestión",
    )

    case = create_case(session, data)
    session.commit()
    context = case_context(case)

    assert case.ai_application == "Infraestructura tecnológica y acceso remoto"
    assert context["objective"] == case.description
    assert context["analysis_scope"] == case.ai_application
    assert context["data_involved"] is None
    assert context["restrictions"] is None
    assert sorted(asset.name for asset in list_assets(session, case.id)) == [
        "servidor-de-gestión",
        "vpn",
    ]


def test_existing_ai_scope_content_is_preserved(session) -> None:
    data = CaseInput.from_form(
        title="Evaluación de un asistente de IA",
        ai_application="Asistente interno de consulta documental",
    )

    case = create_case(session, data)
    session.commit()

    assert case.ai_application == "Asistente interno de consulta documental"
    assert case_context(case)["analysis_scope"] == "Asistente interno de consulta documental"


def test_case_context_reports_unknown_fields_as_none(session) -> None:
    case = create_case(session, CaseInput.from_form(title="Caso mínimo"))
    session.commit()

    assert case_context(case) == {
        "title": "Caso mínimo",
        "objective": None,
        "analysis_scope": None,
        "data_involved": None,
        "restrictions": None,
    }


def test_list_and_get_case(session) -> None:
    first = create_case(session, CaseInput.from_form(title="Primero"))
    second = create_case(session, CaseInput.from_form(title="Segundo"))
    session.commit()

    cases = list_cases(session)
    scope = resolve_case_scope(session, second.id)

    assert [case.title for case in cases][:2] == ["Segundo", "Primero"]
    assert get_case(session, scope).id == second.id
    assert get_case(session, scope).id != first.id


def test_unknown_case_is_rejected(session) -> None:
    with pytest.raises(CaseNotFoundError):
        resolve_case_scope(session, "0" * 32)


def test_display_value_marks_unknown() -> None:
    assert display_value(None) == "Desconocido"
    assert display_value("   ") == "Desconocido"
    assert display_value("texto") == "texto"
