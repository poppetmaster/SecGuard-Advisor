"""Contrato de la interfaz de findings_query en la consulta documental."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from tests.fixtures.corpus import create_case
from tests.fixtures.fakes import FakeEmbedder, FakeTokenCounter, ScriptedGenerator
from tests.fixtures.findings import seed_findings

from secguard_advisor.config import Settings
from secguard_advisor.conversation.llm import AnswerPayload, ToolDecision
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.retrieval.index import ChromaIndex
from secguard_advisor.web.app import create_app

ORIGIN = {"Origin": "http://testserver"}
HTMX = {**ORIGIN, "HX-Request": "true"}

FINDINGS = [
    ("api-gateway", "High", "900001", []),
    ("api-gateway", "High", "900002", []),
    ("portal", "High", "900003", ["CVE-2024-0001"]),
    ("portal", "Low", "900004", []),
]


def _use(arguments: dict) -> ToolDecision:
    return ToolDecision(use_findings=True, arguments=arguments)


def _no_tool() -> ToolDecision:
    return ToolDecision(use_findings=False, arguments={})


def _answer(text: str = "Hay 3 hallazgos de severidad High.") -> AnswerPayload:
    return AnswerPayload(answer=text, claims=[])


def _app(settings, index, generator):
    return create_app(
        settings,
        ollama_probe=lambda: True,
        embedder_factory=lambda: FakeEmbedder(),
        index_factory=lambda: index,
        llm_factory=lambda: generator,
        token_counter=FakeTokenCounter(),
    )


@pytest.fixture
def context(tmp_path: Path):
    settings = Settings(_env_file=None, storage_dir=tmp_path / "storage")
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        case_id = create_case(session, "Caso de hallazgos")
        session.commit()
    index = ChromaIndex(settings.chroma_dir)
    yield settings, factory, case_id, index
    engine.dispose()


def _ask(client: TestClient, case_id: str):
    return client.post(
        f"/cases/{case_id}/chat/messages",
        data={"question": "¿Cuántos hallazgos High hay y cómo se agrupan por activo?"},
        headers=HTMX,
    )


def test_tool_result_is_presented_with_synthetic_provenance(context) -> None:
    settings, factory, case_id, index = context
    seeded = seed_findings(factory, findings=FINDINGS, case_id=case_id)
    generator = ScriptedGenerator(
        payloads=[_answer()],
        decisions=[_use({"severity": "High", "group_by": "asset"}), _no_tool()],
    )

    with TestClient(_app(settings, index, generator)) as client:
        response = _ask(client, case_id)

    assert response.status_code == 200
    html = response.text
    assert "Herramienta consultada" in html
    assert "findings_query" in html
    assert "Datos educativos sintéticos" in html
    assert "Total:" in html and "3" in html
    assert "severity=High" in html and "group_by=asset" in html
    assert "api-gateway" in html and "portal" in html
    assert seeded.dataset_name in html
    assert "no una importación de Qualys" in html


def test_detail_is_shown_with_limit_notice(context) -> None:
    settings, factory, case_id, index = context
    seed_findings(factory, findings=FINDINGS, case_id=case_id)
    generator = ScriptedGenerator(
        payloads=[_answer("Hay 4 hallazgos.")],
        decisions=[_use({"detail": True, "limit": 2}), _no_tool()],
    )

    with TestClient(_app(settings, index, generator)) as client:
        response = _ask(client, case_id)

    html = response.text
    assert "Detalle limitado a 2 filas" in html
    assert "Componente desactualizado" not in html  # no se inventan títulos
    assert "Hallazgo 900001" in html
    assert "900004" not in html


def test_run_evidence_page_shows_the_tool_call(context) -> None:
    settings, factory, case_id, index = context
    seed_findings(factory, findings=FINDINGS, case_id=case_id)
    generator = ScriptedGenerator(
        payloads=[_answer("Hay 3 hallazgos High.")],
        decisions=[_use({"severity": "High"}), _no_tool()],
    )

    with TestClient(_app(settings, index, generator)) as client:
        _ask(client, case_id)
        with factory() as session:
            from sqlalchemy import select

            from secguard_advisor.db.models import Run

            run_id = session.scalar(select(Run.id).where(Run.case_id == case_id))
        page = client.get(f"/cases/{case_id}/runs/{run_id}")

    assert page.status_code == 200
    assert "Herramientas" in page.text
    assert "findings_query" in page.text
    assert "Datos educativos sintéticos" in page.text


def test_empty_case_explains_that_absence_is_not_low_risk(context) -> None:
    settings, _factory, case_id, index = context
    generator = ScriptedGenerator(
        payloads=[_answer("No hay hallazgos registrados.")],
        decisions=[_use({}), _no_tool()],
    )

    with TestClient(_app(settings, index, generator)) as client:
        response = _ask(client, case_id)

    html = response.text
    assert "Sin dataset asociado" in html
    assert "no demuestra ausencia de vulnerabilidades" in html
    assert "Total:" in html


def test_invalid_tool_arguments_are_visible_as_an_error(context) -> None:
    settings, factory, case_id, index = context
    seed_findings(factory, findings=FINDINGS, case_id=case_id)
    generator = ScriptedGenerator(
        payloads=[_answer("No pude consultar los hallazgos.")],
        decisions=[_use({"severity": "Baja"}), _no_tool()],
    )

    with TestClient(_app(settings, index, generator)) as client:
        response = _ask(client, case_id)

    html = response.text
    assert "Argumentos inválidos" in html
    assert "invalid_severity" in html
