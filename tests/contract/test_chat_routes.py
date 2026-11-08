"""Pruebas de contrato de la conversación documental."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from tests.fixtures.corpus import seed_document
from tests.fixtures.fakes import FakeEmbedder

from secguard_advisor.config import Settings
from secguard_advisor.conversation.concurrency import GenerationSlot
from secguard_advisor.conversation.llm import (
    AnswerPayload,
    Claim,
    ModelTimeout,
    ModelUnavailable,
)
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import Case, Conversation, Message, Run, new_id
from secguard_advisor.retrieval.index import ChromaIndex
from secguard_advisor.web.app import create_app

ORIGIN = {"Origin": "http://testserver"}
HTMX = {**ORIGIN, "HX-Request": "true"}
TEXT = (
    "El marco de ciberseguridad define seis funciones centrales: gobernar, identificar, "
    "proteger, detectar, responder y recuperar."
)


class ScriptedGenerator:
    """Generador guionizado con respuestas o fallos controlados."""

    model = "fake-generator"
    digest = "digest-fake"

    def __init__(self, *, payload=None, error: Exception | None = None) -> None:
        self.payload = payload
        self.error = error
        self.calls = 0

    def generate(self, *, system: str, user: str) -> AnswerPayload:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.payload or AnswerPayload(answer="respuesta", claims=[])


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        storage_dir=tmp_path / "storage",
        generation_queue_timeout_seconds=0.2,
    )


def _prepare(settings: Settings) -> None:
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    engine.dispose()


def _app(settings: Settings, index, generator, slot=None):
    return create_app(
        settings,
        ollama_probe=lambda: True,
        embedder_factory=lambda: FakeEmbedder(),
        index_factory=lambda: index,
        llm_factory=lambda: generator,
        generation_slot=slot,
    )


@pytest.fixture
def context(tmp_path: Path):
    settings = _settings(tmp_path)
    _prepare(settings)
    index = ChromaIndex(tmp_path / "chroma")
    engine = create_engine_for_url(settings.database_url)
    factory = create_session_factory(engine)
    with factory() as session:
        case = Case(title="Caso de chat", synthetic_notice="Escenario educativo")
        session.add(case)
        session.commit()
        case_id = case.id
    seeded = seed_document(
        factory,
        texts=[TEXT],
        index=index,
        embedder=FakeEmbedder(),
        case_id=case_id,
        pages=[12],
    )
    public = seed_document(
        factory,
        texts=["Guía pública sobre funciones de ciberseguridad."],
        index=index,
        embedder=FakeEmbedder(),
        source_id="csf2",
        pages=[2],
    )
    yield settings, factory, case_id, seeded, public, index, engine
    engine.dispose()


def _payload(seeded, quote: str, answer: str = "El marco define seis funciones.") -> AnswerPayload:
    return AnswerPayload(
        answer=answer,
        claims=[Claim(text=answer, chunk_ids=[seeded.chunk_ids[0]], quote=quote)],
    )


def _ask(client: TestClient, case_id: str, question: str = "¿Qué funciones define?"):
    return client.post(
        f"/cases/{case_id}/chat/messages",
        data={"question": question},
        headers=HTMX,
    )


def test_question_with_valid_citation_returns_200(context) -> None:
    settings, factory, case_id, seeded, _public, index, _engine = context
    generator = ScriptedGenerator(payload=_payload(seeded, "funciones centrales"))
    app = _app(settings, index, generator)

    with TestClient(app) as client:
        panel = client.get(f"/cases/{case_id}/chat")
        response = _ask(client, case_id)

    assert panel.status_code == 200
    assert response.status_code == 200
    assert "El marco define seis funciones." in response.text
    assert "funciones centrales" in response.text
    assert "Borrador no revisado" in response.text
    assert "válida" in response.text
    assert "pendiente de revisión" in response.text
    assert f"/cases/{case_id}/documents/{seeded.document_id}/versions/" in response.text

    with factory() as session:
        run = session.scalar(select(Run).where(Run.case_id == case_id))
        citations = session.scalar(
            select(func.count()).select_from(
                __import__(
                    "secguard_advisor.db.models", fromlist=["MessageCitation"]
                ).MessageCitation
            )
        )
        assert run.status == "succeeded"
        assert run.outcome == "answered"
        assert run.answer_message_id is not None
        assert citations == 1


def test_empty_question_returns_422_without_run(context) -> None:
    settings, factory, case_id, seeded, _public, index, _engine = context
    generator = ScriptedGenerator(payload=_payload(seeded, "funciones centrales"))
    app = _app(settings, index, generator)

    with TestClient(app) as client:
        response = _ask(client, case_id, question="   ")

    assert response.status_code == 422
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Run)) == 0
        assert session.scalar(select(func.count()).select_from(Message)) == 0


def test_active_case_returns_409_without_new_run(context) -> None:
    settings, factory, case_id, seeded, _public, index, _engine = context
    generator = ScriptedGenerator(payload=_payload(seeded, "funciones centrales"))
    app = _app(settings, index, generator)

    with TestClient(app) as client:
        # La ejecución activa se crea con la aplicación ya iniciada: la reconciliación
        # de arranque marca como interrumpida cualquier ejecución previa.
        with factory() as session:
            conversation = Conversation(case_id=case_id, thread_id=new_id())
            session.add(conversation)
            session.flush()
            question = Message(
                conversation_id=conversation.id,
                seq=1,
                role="user",
                content="pregunta previa",
                status="complete",
            )
            session.add(question)
            session.flush()
            session.add(
                Run(
                    case_id=case_id,
                    conversation_id=conversation.id,
                    question_message_id=question.id,
                    status="running",
                    generator_model="fake",
                    generator_num_ctx=8192,
                    generator_temperature=0.1,
                    embedding_model="fake-embedding",
                    embedding_dim=4,
                    prompt_version="chat-v1",
                )
            )
            session.commit()

        response = _ask(client, case_id)

    assert response.status_code == 409
    assert response.text.lstrip().startswith('<section id="chat-panel"')
    assert "consulta en curso" in response.text
    assert generator.calls == 0
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Run)) == 1


def test_global_saturation_returns_429_without_run(context) -> None:
    settings, factory, case_id, seeded, _public, index, _engine = context
    generator = ScriptedGenerator(payload=_payload(seeded, "funciones centrales"))
    slot = GenerationSlot(timeout_seconds=0.05)
    app = _app(settings, index, generator, slot=slot)
    assert slot.acquire() is True
    try:
        with TestClient(app) as client:
            response = _ask(client, case_id)
    finally:
        slot.release()

    assert response.status_code == 429
    assert response.text.lstrip().startswith('<section id="chat-panel"')
    assert "El sistema está ocupado" in response.text
    assert generator.calls == 0
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Run)) == 0
        assert session.scalar(select(func.count()).select_from(Message)) == 0


def test_model_unavailable_returns_503(context) -> None:
    settings, factory, case_id, _seeded, _public, index, _engine = context
    generator = ScriptedGenerator(error=ModelUnavailable("no responde"))
    app = _app(settings, index, generator)

    with TestClient(app) as client:
        response = _ask(client, case_id)

    assert response.status_code == 503
    assert response.text.lstrip().startswith('<section id="chat-panel"')
    assert "El modelo local no responde" in response.text
    with factory() as session:
        run = session.scalar(select(Run).where(Run.case_id == case_id))
        assert run.status == "failed"
        assert run.error_code == "model_unavailable"
        assert run.answer_message_id is None


def test_model_timeout_returns_504(context) -> None:
    settings, factory, case_id, _seeded, _public, index, _engine = context
    generator = ScriptedGenerator(error=ModelTimeout("timeout"))
    app = _app(settings, index, generator)

    with TestClient(app) as client:
        response = _ask(client, case_id)

    assert response.status_code == 504
    assert response.text.lstrip().startswith('<section id="chat-panel"')
    assert "excedió el tiempo" in response.text
    with factory() as session:
        run = session.scalar(select(Run).where(Run.case_id == case_id))
        assert run.status == "timeout"
        assert run.error_code == "run_timeout"


def test_panel_shows_sources_with_provenance(context) -> None:
    settings, _factory, case_id, seeded, _public, index, _engine = context
    generator = ScriptedGenerator(payload=_payload(seeded, "funciones centrales"))
    app = _app(settings, index, generator)

    with TestClient(app) as client:
        response = _ask(client, case_id)

    assert response.status_code == 200
    assert "Fragmentos recuperados" in response.text
    assert "Evidencia del caso" in response.text
    assert "citado en la respuesta" in response.text


def test_run_evidence_page_is_scoped_to_the_case(context) -> None:
    settings, factory, case_id, seeded, _public, index, _engine = context
    generator = ScriptedGenerator(payload=_payload(seeded, "funciones centrales"))
    app = _app(settings, index, generator)

    with TestClient(app) as client:
        _ask(client, case_id)
        with factory() as session:
            run = session.scalar(select(Run).where(Run.case_id == case_id))
            run_id = run.id
        page = client.get(f"/cases/{case_id}/runs/{run_id}")
        with factory() as session:
            other = Case(title="Otro caso", synthetic_notice="Escenario educativo")
            session.add(other)
            session.commit()
            other_id = other.id
        foreign = client.get(f"/cases/{other_id}/runs/{run_id}")

    assert page.status_code == 200
    assert "Evidencia de ejecución" in page.text
    assert "fake-generator" in page.text
    assert "load_scope" in page.text
    assert foreign.status_code == 404
