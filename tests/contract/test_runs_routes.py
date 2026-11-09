"""Contrato de la página «Ver ejecución»."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from tests.fixtures.conversation import build_env
from tests.fixtures.fakes import FakeEmbedder, FakeTokenCounter, ScriptedGenerator
from tests.fixtures.findings import seed_findings

from secguard_advisor.conversation.llm import (
    AnswerPayload,
    Claim,
    ModelUnavailable,
    ToolDecision,
)
from secguard_advisor.db.models import MessageCitation, Run
from secguard_advisor.web.app import create_app

ORIGIN = {"Origin": "http://testserver"}
HTMX = {**ORIGIN, "HX-Request": "true"}


def _app(env, generator):
    return create_app(
        env.settings,
        ollama_probe=lambda: True,
        embedder_factory=lambda: FakeEmbedder(),
        index_factory=lambda: env.index,
        llm_factory=lambda: generator,
        token_counter=FakeTokenCounter(),
    )


def _ask(client: TestClient, case_id: str):
    return client.post(
        f"/cases/{case_id}/chat/messages",
        data={"question": "¿Qué controles aplican?"},
        headers=HTMX,
    )


def _run_id(env, case_id: str, attempt_no: int = 1) -> str:
    with env.factory() as session:
        return session.scalar(
            select(Run.id)
            .where(Run.case_id == case_id, Run.attempt_no == attempt_no)
            .order_by(Run.started_at)
        )


def _answer(env) -> AnswerPayload:
    if not env.public_document.chunk_ids:
        return AnswerPayload(answer="respuesta", claims=[])
    return AnswerPayload(
        answer="El marco define seis funciones centrales.",
        claims=[
            Claim(
                text="El marco define seis funciones.",
                chunk_ids=[env.public_document.chunk_ids[0]],
                quote="seis funciones centrales",
            )
        ],
    )


def test_documentary_run_shows_model_steps_sources_and_both_controls(tmp_path: Path) -> None:
    env = build_env(tmp_path)
    generator = ScriptedGenerator([_answer(env)])

    with TestClient(_app(env, generator)) as client:
        _ask(client, env.case_id)
        run_id = _run_id(env, env.case_id)
        page = client.get(f"/cases/{env.case_id}/runs/{run_id}")

    assert page.status_code == 200
    html = page.text
    assert "Modelo y configuración" in html
    assert "fake-generator" in html
    assert "chat-v7" in html
    assert "Pasos" in html
    assert "Generación" in html
    assert "Control automático de citas" in html
    assert "Control automático: válida" in html
    assert "Revisión humana: pendiente de revisión" in html
    assert "Un control automático válido no acredita respaldo semántico" in html
    assert "Fuentes recuperadas" in html
    assert "The NIST Cybersecurity Framework" in html
    assert "citado en la respuesta" in html
    assert "Traceback" not in html


def test_tool_run_separates_historical_summary_from_current_detail(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    seed_findings(
        env.factory,
        case_id=env.case_id,
        findings=[("api-gateway", "High", "900001", [])],
    )
    generator = ScriptedGenerator(
        payloads=[AnswerPayload(answer="Hay 1 hallazgo High.", claims=[])],
        decisions=[
            ToolDecision(use_findings=True, arguments={"severity": "High", "detail": True}),
            ToolDecision(use_findings=False, arguments={}),
        ],
    )

    with TestClient(_app(env, generator)) as client:
        _ask(client, env.case_id)
        run_id = _run_id(env, env.case_id)
        page = client.get(f"/cases/{env.case_id}/runs/{run_id}")

    assert page.status_code == 200
    html = page.text
    assert "findings_query" in html
    assert "Datos educativos sintéticos" in html
    assert "Consulta actual:" in html
    assert "detalle recalculado al abrir esta página" in html
    assert "api-gateway" in html
    assert "Sin citas documentales" in html
    assert "respuesta se respalda con el resultado estructurado" in html


def test_failed_run_shows_error_and_retry(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    generator = ScriptedGenerator(error=ModelUnavailable("caído"))

    with TestClient(_app(env, generator)) as client:
        _ask(client, env.case_id)
        run_id = _run_id(env, env.case_id)
        page = client.get(f"/cases/{env.case_id}/runs/{run_id}")

    assert page.status_code == 200
    html = page.text
    assert "El modelo local no responde." in html
    assert "model_unavailable" in html
    assert "Reintentar la pregunta" in html
    assert f"/cases/{env.case_id}/chat" in html
    assert "El reintento está disponible en la conversación" in html


def test_second_attempt_links_to_the_first(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    failing = ScriptedGenerator(error=ModelUnavailable("caído"))

    with TestClient(_app(env, failing)) as client:
        _ask(client, env.case_id)
        first_id = _run_id(env, env.case_id)

    retry_generator = ScriptedGenerator([_answer(env)])
    with TestClient(_app(env, retry_generator)) as client:
        client.post(
            f"/cases/{env.case_id}/runs/{first_id}/retry",
            headers=HTMX,
        )
        second_id = _run_id(env, env.case_id, attempt_no=2)
        page = client.get(f"/cases/{env.case_id}/runs/{second_id}")

    assert page.status_code == 200
    html = page.text
    assert "Intentos de esta pregunta" in html
    assert "Intento 1" in html
    assert "Intento 2 (actual)" in html
    assert f"/cases/{env.case_id}/runs/{first_id}" in html
    assert "reintento de" in html


@pytest.mark.parametrize(
    ("status", "label"),
    [
        ("disabled", "No configurada"),
        ("submitted", "Enviada (no verificada)"),
        ("failed", "No disponible"),
    ],
)
def test_trace_status_is_presented_without_claiming_verification(
    tmp_path: Path, status: str, label: str
) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    generator = ScriptedGenerator([_answer(env)])

    with TestClient(_app(env, generator)) as client:
        _ask(client, env.case_id)
        run_id = _run_id(env, env.case_id)
        with env.factory() as session:
            run = session.get(Run, run_id)
            run.trace_status = status
            run.trace_id = "trace-1" if status != "disabled" else None
            run.trace_url = "https://smith.test/trace-1" if status == "submitted" else None
            session.commit()
        page = client.get(f"/cases/{env.case_id}/runs/{run_id}")

    html = page.text
    assert label in html
    assert "Traza verificada" not in html
    if status == "submitted":
        assert "https://smith.test/trace-1" in html
        assert "No significa que la traza esté verificada" in html


def test_run_from_another_case_is_not_found(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    generator = ScriptedGenerator([_answer(env)])

    with TestClient(_app(env, generator)) as client:
        _ask(client, env.case_id)
        run_id = _run_id(env, env.case_id)
        with env.factory() as session:
            from tests.fixtures.corpus import create_case

            other_id = create_case(session, "Otro caso")
            session.commit()
        foreign = client.get(f"/cases/{other_id}/runs/{run_id}")

    assert foreign.status_code == 404


def test_human_review_is_shown_separately_from_the_automatic_check(tmp_path: Path) -> None:
    env = build_env(tmp_path)
    generator = ScriptedGenerator([_answer(env)])

    with TestClient(_app(env, generator)) as client:
        _ask(client, env.case_id)
        run_id = _run_id(env, env.case_id)
        with env.factory() as session:
            citation = session.scalar(select(MessageCitation))
            citation.support_review_status = "supported"
            citation.support_reviewed_by = "Revisora"
            citation.support_reviewed_at = "2026-11-09T01:00:00Z"
            citation.support_review_note = "Sostiene la afirmación."
            session.commit()
        page = client.get(f"/cases/{env.case_id}/runs/{run_id}")

    html = page.text
    assert "Control automático: válida" in html
    assert "Revisión humana: respaldada" in html
    assert "Revisora" in html
    assert "Sostiene la afirmación." in html
    assert "1 revisada(s) · 0 pendiente(s)" in html


def test_chat_reload_offers_retry_for_the_latest_failure(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    generator = ScriptedGenerator(error=ModelUnavailable("caído"))

    with TestClient(_app(env, generator)) as client:
        _ask(client, env.case_id)
        page = client.get(f"/cases/{env.case_id}/chat")

    assert page.status_code == 200
    html = page.text
    assert "Reintentar la pregunta" in html
    assert f"/cases/{env.case_id}/runs/" in html
    assert "El modelo local no responde." in html


def test_confirmed_trace_shows_declared_identity_and_date(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    generator = ScriptedGenerator([_answer(env)])

    with TestClient(_app(env, generator)) as client:
        _ask(client, env.case_id)
        run_id = _run_id(env, env.case_id)
        with env.factory() as session:
            run = session.get(Run, run_id)
            run.trace_status = "confirmed"
            run.trace_id = "trace-1"
            run.trace_url = "https://smith.test/trace-1"
            run.trace_confirmed_by = "Aceptación de prueba"
            run.trace_confirmed_at = "2026-11-09T06:49:26Z"
            session.commit()
        page = client.get(f"/cases/{env.case_id}/runs/{run_id}")

    html = page.text
    assert "Traza verificada" in html
    assert "Aceptación de prueba" in html
    assert "2026-11-09T06:49:26Z" in html
    assert "Enviada (no verificada)" not in html
    assert "https://smith.test/trace-1" in html
