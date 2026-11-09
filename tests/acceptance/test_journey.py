"""Aceptación integrada con dobles rápidos, sin Ollama ni credenciales externas.

Dobles usados:
- `FakeEmbedder`: vectores deterministas; no llama a Ollama.
- `FakeTokenCounter`: conteo aproximado por bytes; no carga el tokenizador real.
- `ScriptedGenerator`: respuestas y decisiones guionizadas; no llama al modelo.
- `ChromaIndex`: índice local temporal con los vectores del doble.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from tests.fixtures.conversation import build_env
from tests.fixtures.fakes import FakeEmbedder, FakeTokenCounter, ScriptedGenerator
from tests.fixtures.findings import seed_findings

from secguard_advisor.conversation.concurrency import GenerationSlot
from secguard_advisor.conversation.llm import AnswerPayload, Claim, ModelUnavailable, ToolDecision
from secguard_advisor.conversation.service import (
    create_question_message,
    get_or_create_conversation,
)
from secguard_advisor.db.models import (
    DocumentChunk,
    Message,
    MessageCitation,
    Run,
)
from secguard_advisor.evidence.runs import create_run
from secguard_advisor.web.app import create_app

ORIGIN = {"Origin": "http://testserver"}
HTMX = {**ORIGIN, "HX-Request": "true"}
POLICY = (
    "# Política de respaldo\n\n"
    "La organización realiza copias de seguridad cifradas cada 24 horas y prueba la restauración "
    "trimestralmente. El responsable de infraestructura conserva el registro de cada prueba.\n"
)


def _app(env, generator, slot=None):
    return create_app(
        env.settings,
        ollama_probe=lambda: True,
        embedder_factory=lambda: FakeEmbedder(),
        index_factory=lambda: env.index,
        llm_factory=lambda: generator,
        generation_slot=slot,
        token_counter=FakeTokenCounter(),
    )


def _create_case(client: TestClient, title: str) -> str:
    response = client.post(
        "/cases",
        data={"title": title},
        headers=ORIGIN,
        follow_redirects=False,
    )
    assert response.status_code == 303
    return response.headers["location"].split("/")[-1]


def _upload_policy(client: TestClient, case_id: str) -> None:
    response = client.post(
        f"/cases/{case_id}/documents",
        files={"file": ("politica.md", POLICY.encode("utf-8"), "text/markdown")},
        data={"title": "Política de respaldo"},
        headers=HTMX,
    )
    assert response.status_code == 201
    assert "Disponible" in response.text


def _ask(client: TestClient, case_id: str, question: str):
    return client.post(
        f"/cases/{case_id}/chat/messages",
        data={"question": question},
        headers=HTMX,
    )


def _case_chunk(env, case_id: str) -> tuple[str, str]:
    with env.factory() as session:
        chunk = session.scalar(
            select(DocumentChunk).where(DocumentChunk.text.contains("restauración"))
        )
        assert chunk is not None
        return chunk.id, chunk.text


def _run_for_question(env, case_id: str, question: str) -> Run:
    with env.factory() as session:
        message = session.scalar(
            select(Message)
            .where(Message.content == question, Message.role == "user")
            .order_by(Message.seq.desc())
        )
        assert message is not None
        run = session.scalar(
            select(Run).where(Run.question_message_id == message.id).order_by(Run.attempt_no.desc())
        )
        assert run is not None
        return run


def test_integrated_journey_with_fast_doubles(tmp_path: Path) -> None:
    env = build_env(
        tmp_path,
        with_documents=False,
        min_score=-1.0,
        settings_overrides={
            "reviewer_name": "Revisora de prueba",
            "generation_queue_timeout_seconds": 0.2,
        },
    )
    generator = ScriptedGenerator(
        payloads=[
            AnswerPayload(
                answer="La restauración se prueba trimestralmente.",
                claims=[
                    Claim(
                        text="La restauración se prueba trimestralmente.",
                        quote="prueba la restauración trimestralmente",
                    )
                ],
            ),
            AnswerPayload(
                answer="El responsable de infraestructura conserva el registro.",
                claims=[
                    Claim(
                        text="El responsable conserva el registro.",
                        quote="El responsable de infraestructura conserva el registro",
                    )
                ],
            ),
            AnswerPayload(answer="Hay 3 hallazgos High: 2 en api y 1 en portal.", claims=[]),
            AnswerPayload(answer="No hay evidencia documental.", claims=[]),
            AnswerPayload(answer="No hay hallazgos registrados.", claims=[]),
        ],
        decisions=[
            ToolDecision(use_findings=False, arguments={}),
            ToolDecision(use_findings=False, arguments={}),
            ToolDecision(use_findings=True, arguments={"severity": "High", "group_by": "asset"}),
            ToolDecision(use_findings=False, arguments={}),
            ToolDecision(use_findings=False, arguments={}),
            ToolDecision(use_findings=True, arguments={}),
            ToolDecision(use_findings=False, arguments={}),
        ],
    )

    with TestClient(_app(env, generator)) as client:
        case_id = _create_case(client, "Caso de aceptación rápida")
        _upload_policy(client, case_id)
        chunk_id, _text = _case_chunk(env, case_id)
        # El generador no conoce el chunk hasta después de la carga.
        generator.payloads[0].claims[0].chunk_ids = [chunk_id]
        generator.payloads[1].claims[0].chunk_ids = [chunk_id]
        seed_findings(
            env.factory,
            case_id=case_id,
            findings=[
                ("api", "High", "900001", []),
                ("api", "High", "900002", []),
                ("portal", "High", "900003", []),
                ("portal", "Low", "900004", []),
            ],
        )

        first = _ask(client, case_id, "¿Cada cuánto se prueba la restauración?")
        assert first.status_code == 200
        assert "La restauración se prueba trimestralmente." in first.text
        assert "Control automático" in first.text
        assert "Respaldo semántico: pendiente de revisión" in first.text

        followup = _ask(client, case_id, "¿Quién conserva el registro?")
        assert followup.status_code == 200
        assert "El responsable de infraestructura conserva el registro." in followup.text
        assert generator.prompts[1].count("Pregunta actual") == 1
        assert "¿Cada cuánto se prueba la restauración?" in generator.prompts[1]

        findings = _ask(client, case_id, "¿Cuántos hallazgos High hay por activo?")
        assert findings.status_code == 200
        assert "Total:" in findings.text and "3" in findings.text
        assert "api" in findings.text and "portal" in findings.text
        assert "Datos educativos sintéticos" in findings.text

        empty_case = _create_case(client, "Caso vacío")
        abstention = _ask(client, empty_case, "¿Qué dice el NIST sobre una norma inexistente?")
        assert abstention.status_code == 200
        assert "No encontré evidencia documental suficiente" in abstention.text
        empty_findings = _ask(client, empty_case, "¿Hay hallazgos High en este caso?")
        assert empty_findings.status_code == 200
        assert "Total:" in empty_findings.text and "0" in empty_findings.text
        assert "no demuestra ausencia de vulnerabilidades" in empty_findings.text

        # Revisión humana: se registra por cita y con identidad declarada.
        with env.factory() as session:
            first_run = session.scalar(
                select(Run).where(Run.case_id == case_id).order_by(Run.started_at)
            )
            citation = session.scalar(
                select(MessageCitation).where(
                    MessageCitation.message_id == first_run.answer_message_id
                )
            )
            assert citation is not None
            message_id = citation.message_id
            citation_id = citation.id
        reviewed = client.post(
            f"/cases/{case_id}/messages/{message_id}/citations/{citation_id}/review",
            data={"status": "supported", "note": "El fragmento sostiene la afirmación."},
            headers=HTMX,
        )
        assert reviewed.status_code == 200
        with env.factory() as session:
            stored = session.get(MessageCitation, citation_id)
            assert stored.support_review_status == "supported"
            assert stored.support_reviewed_by == "Revisora de prueba"
            assert stored.support_reviewed_at

        # La conversación del primer caso no filtra el segundo y viceversa.
        first_chat = client.get(f"/cases/{case_id}/chat")
        second_chat = client.get(f"/cases/{empty_case}/chat")
        assert "¿Hay hallazgos High en este caso?" not in first_chat.text
        assert "¿Cada cuánto se prueba la restauración?" not in second_chat.text
        assert "Caso vacío" in second_chat.text

    # Reinicio: nueva aplicación sobre el mismo almacenamiento.
    restart_generator = ScriptedGenerator([AnswerPayload(answer="respuesta", claims=[])])
    with TestClient(_app(env, restart_generator)) as restarted:
        history = restarted.get(f"/cases/{case_id}/chat")
        assert history.status_code == 200
        assert "¿Cada cuánto se prueba la restauración?" in history.text
        assert "¿Quién conserva el registro?" in history.text
        assert "¿Cuántos hallazgos High hay por activo?" in history.text
        with env.factory() as session:
            run = session.scalar(select(Run).where(Run.case_id == case_id).order_by(Run.started_at))
            run_id = run.id
        evidence = restarted.get(f"/cases/{case_id}/runs/{run_id}")
        assert evidence.status_code == 200
        assert "Control automático: válida" in evidence.text
        assert "Revisión humana: respaldada" in evidence.text
        assert "Revisora de prueba" in evidence.text
        assert "No configurada" in evidence.text


def test_retry_then_new_question_is_distinct(tmp_path: Path) -> None:
    env = build_env(
        tmp_path,
        with_documents=False,
        min_score=-1.0,
        settings_overrides={"generation_queue_timeout_seconds": 0.2},
    )
    failing = ScriptedGenerator(error=ModelUnavailable("caído"))
    with TestClient(_app(env, failing)) as client:
        case_id = _create_case(client, "Caso de reintento")
        _ask(client, case_id, "¿Qué controles aplican?")
        with env.factory() as session:
            failed = session.scalar(
                select(Run).where(Run.case_id == case_id).order_by(Run.started_at)
            )
            assert failed is not None
            failed_id = failed.id
            question_id = failed.question_message_id

    working = ScriptedGenerator([AnswerPayload(answer="respuesta nueva", claims=[])])
    with TestClient(_app(env, working)) as client:
        retried = client.post(f"/cases/{case_id}/runs/{failed_id}/retry", headers=HTMX)
        assert retried.status_code == 202
        with env.factory() as session:
            retry_run = session.scalar(
                select(Run).where(Run.case_id == case_id).order_by(Run.attempt_no.desc())
            )
            assert retry_run.attempt_no == 2
            assert retry_run.retry_of_run_id == failed_id
            assert retry_run.question_message_id == question_id

        new_question = _ask(client, case_id, "¿Y qué otra cosa aplica?")
        assert new_question.status_code == 200
        with env.factory() as session:
            total_questions = session.scalar(
                select(func.count()).select_from(Message).where(Message.role == "user")
            )
            runs = list(
                session.scalars(select(Run).where(Run.case_id == case_id).order_by(Run.started_at))
            )
    assert total_questions == 2
    assert [run.attempt_no for run in runs] == [1, 2, 1]


def test_duplicate_and_global_busy_are_rejected(tmp_path: Path) -> None:
    env = build_env(
        tmp_path,
        with_documents=False,
        min_score=-1.0,
        settings_overrides={"generation_queue_timeout_seconds": 0.1},
    )
    generator = ScriptedGenerator([AnswerPayload(answer="respuesta", claims=[])])
    slot = GenerationSlot(0.1)
    with TestClient(_app(env, generator, slot)) as client:
        case_id = _create_case(client, "Caso de concurrencia")
        with env.factory() as session:
            conversation = get_or_create_conversation(session, case_id)
            question = create_question_message(session, conversation.id, "pregunta activa")
            create_run(
                session,
                case_id=case_id,
                conversation_id=conversation.id,
                question_message_id=question.id,
                generator_model=env.settings.ollama_model,
                generator_num_ctx=env.settings.generator_num_ctx,
                generator_temperature=env.settings.generator_temperature,
                embedding_model=env.settings.ollama_embedding_model,
                embedding_dim=env.settings.embedding_dim,
                prompt_version="chat-v4",
            )
            session.commit()

        duplicate = _ask(client, case_id, "otra pregunta")
        assert duplicate.status_code == 409
        assert "consulta en curso" in duplicate.text

        other_case = _create_case(client, "Caso libre")
        assert slot.acquire()
        try:
            busy = _ask(client, other_case, "pregunta con permiso ocupado")
        finally:
            slot.release()
        assert busy.status_code == 429
        assert "ocupado" in busy.text
