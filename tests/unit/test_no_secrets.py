"""Secretos, rutas absolutas y trazas de pila fuera de respuestas y registros."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from tests.fixtures.conversation import build_env
from tests.fixtures.fakes import FakeEmbedder, FakeTokenCounter, ScriptedGenerator

from secguard_advisor.conversation.llm import AnswerPayload, ModelUnavailable
from secguard_advisor.db.models import Run
from secguard_advisor.logging import ContextFilter, log_event
from secguard_advisor.web.app import create_app

ORIGIN = {"Origin": "http://testserver"}
HTMX = {**ORIGIN, "HX-Request": "true"}
DECOY_KEY = "lsv2_decoy_secret_123456789"
DECOY_PATH = "/Users/example/caso-privado"


def _app(env, generator):
    return create_app(
        env.settings,
        ollama_probe=lambda: True,
        embedder_factory=lambda: FakeEmbedder(),
        index_factory=lambda: env.index,
        llm_factory=lambda: generator,
        token_counter=FakeTokenCounter(),
    )


def test_log_filter_redacts_message_args_nested_context_and_paths() -> None:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="fallo %s %s",
        args=(DECOY_KEY, DECOY_PATH),
        exc_info=None,
    )
    record.nested = {"authorization": "Bearer decoy", "path": DECOY_PATH}

    ContextFilter().filter(record)

    rendered = record.getMessage() + repr(record.nested)
    assert DECOY_KEY not in rendered
    assert DECOY_PATH not in rendered
    assert "Bearer decoy" not in rendered


def test_log_event_does_not_emit_a_decoy_key_or_path(caplog) -> None:
    caplog.set_level(logging.INFO)
    caplog.handler.addFilter(ContextFilter())
    logger = logging.getLogger("secguard.test")

    log_event(
        logger,
        "prueba",
        api_key=DECOY_KEY,
        nested={"authorization": DECOY_KEY, "detalle": DECOY_PATH},
    )

    text = "\n".join(record.getMessage() for record in caplog.records)
    text += repr([record.__dict__ for record in caplog.records])
    assert DECOY_KEY not in text
    assert DECOY_PATH not in text


def test_error_response_hides_key_paths_and_stack_traces(tmp_path: Path) -> None:
    env = build_env(
        tmp_path,
        with_documents=False,
        min_score=-1.0,
        settings_overrides={
            "langsmith_tracing": False,
            "langsmith_api_key": DECOY_KEY,
        },
    )
    generator = ScriptedGenerator(error=ModelUnavailable("caído en /Users/example"))

    with TestClient(_app(env, generator)) as client:
        response = client.post(
            f"/cases/{env.case_id}/chat/messages",
            data={"question": "¿Qué controles aplican?"},
            headers=HTMX,
        )
        with env.factory() as session:
            run_id = session.scalar(select(Run.id).where(Run.case_id == env.case_id))
        evidence = client.get(f"/cases/{env.case_id}/runs/{run_id}")

    for html in (response.text, evidence.text):
        assert DECOY_KEY not in html
        assert str(tmp_path) not in html
        assert "/Users/example" not in html
        assert "Traceback" not in html
        assert "Authorization" not in html


def test_successful_response_does_not_render_internal_paths_or_keys(tmp_path: Path) -> None:
    env = build_env(
        tmp_path,
        with_documents=False,
        min_score=-1.0,
        settings_overrides={
            "langsmith_tracing": False,
            "langsmith_api_key": DECOY_KEY,
        },
    )
    generator = ScriptedGenerator([AnswerPayload(answer="respuesta sintética", claims=[])])

    with TestClient(_app(env, generator)) as client:
        response = client.post(
            f"/cases/{env.case_id}/chat/messages",
            data={"question": "¿Qué controles aplican?"},
            headers=HTMX,
        )

    assert response.status_code == 200
    assert DECOY_KEY not in response.text
    assert str(tmp_path) not in response.text
    assert "/Users/example" not in response.text
    assert "Traceback" not in response.text


def test_templates_do_not_reference_secrets_or_absolute_paths() -> None:
    templates = Path("src/secguard_advisor/web/templates").rglob("*.html")
    for template in templates:
        text = template.read_text(encoding="utf-8")
        for forbidden in (
            "langsmith_api_key",
            "Authorization",
            "Bearer ",
            "Traceback",
            "/Users/",
        ):
            assert forbidden not in text, f"{template}: {forbidden}"
