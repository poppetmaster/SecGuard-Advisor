"""Integración: flujo de revisión humana del respaldo semántico."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from tests.fixtures.corpus import create_case
from tests.fixtures.fakes import ScriptedGenerator
from tests.fixtures.real_corpus import ingest_one_public_source, real_embedder

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.conversation.llm import AnswerPayload, Claim
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import Case, MessageCitation, new_id
from secguard_advisor.retrieval.index import ChromaIndex
from secguard_advisor.retrieval.search import search_documents
from secguard_advisor.web.app import create_app

pytestmark = pytest.mark.integration

ORIGIN = {"Origin": "http://testserver"}
HTMX = {**ORIGIN, "HX-Request": "true"}
QUESTION = "¿Cuáles son las seis funciones centrales del NIST Cybersecurity Framework 2.0?"


def _app(settings: Settings, payload: AnswerPayload):
    return create_app(
        settings,
        ollama_probe=lambda: True,
        embedder_factory=lambda: real_embedder(settings),
        index_factory=lambda: ChromaIndex(settings.chroma_dir),
        llm_factory=lambda: ScriptedGenerator(payloads=[payload]),
    )


def test_review_flow_keeps_controls_separated(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        storage_dir=tmp_path / "storage",
        reviewer_name="Revisora Local",
    )
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)

    with factory() as session:
        case_id = create_case(session, "Caso de revisión")
        session.commit()

    ingest_one_public_source(settings, factory)
    embedder = real_embedder(settings)
    index = ChromaIndex(settings.chroma_dir)
    try:
        with factory() as session:
            retrieval = search_documents(
                session,
                scope=CaseScope(case_id=case_id),
                query=QUESTION,
                embedder=embedder,
                index=index,
                top_k=3,
                min_score=settings.retrieval_min_score,
            )
        assert retrieval.hits
        hit = retrieval.hits[0]
        quote = hit.text[:150].strip()
        payload = AnswerPayload(
            answer="El marco define seis funciones centrales.",
            claims=[Claim(text="Afirmación", chunk_ids=[hit.chunk_id], quote=quote)],
        )

        with TestClient(_app(settings, payload)) as client:
            response = client.post(
                f"/cases/{case_id}/chat/messages",
                data={"question": QUESTION},
                headers=HTMX,
            )
            assert response.status_code == 200
            page = response.text
            assert "Borrador no revisado" in page
            assert "Control automático" in page and "válida" in page
            assert "pendiente de revisión" in page
            assert "respaldada por" not in page

            with factory() as session:
                citation = session.scalar(select(MessageCitation))
                assert citation is not None
                citation_id = citation.id
                message_id = citation.message_id
                assert citation.support_review_status == "unreviewed"

            # Sin identidad configurada la revisión se rechaza y no se escribe.
            without_identity = Settings(
                _env_file=None,
                storage_dir=settings.storage_dir,
                reviewer_name=None,
            )
            with TestClient(_app(without_identity, payload)) as anonymous:
                denied = anonymous.post(
                    f"/cases/{case_id}/messages/{message_id}/citations/{citation_id}/review",
                    data={"status": "supported", "note": ""},
                    headers=HTMX,
                )
            assert denied.status_code == 409
            with factory() as session:
                assert session.get(MessageCitation, citation_id).support_review_status == (
                    "unreviewed"
                )

            reviewed = client.post(
                f"/cases/{case_id}/messages/{message_id}/citations/{citation_id}/review",
                data={"status": "supported", "note": "El fragmento sostiene la afirmación."},
                headers=HTMX,
            )
            assert reviewed.status_code == 200
            assert "respaldada por Revisora Local" in reviewed.text
            assert "Revisora Local" in reviewed.text
            assert "Control automático" in reviewed.text

            with factory() as session:
                stored = session.get(MessageCitation, citation_id)
                assert stored.support_review_status == "supported"
                assert stored.support_reviewed_by == "Revisora Local"
                assert stored.support_reviewed_at is not None
                assert stored.support_review_note == "El fragmento sostiene la afirmación."

            # Una cita de otro caso no se revela.
            with factory() as session:
                other = Case(title="Otro caso", synthetic_notice="Escenario educativo")
                other.id = new_id()
                session.add(other)
                session.commit()
                other_id = other.id
            foreign = client.post(
                f"/cases/{other_id}/messages/{message_id}/citations/{citation_id}/review",
                data={"status": "supported", "note": ""},
                headers=HTMX,
            )
            assert foreign.status_code == 404

            chat = client.get(f"/cases/{case_id}/chat")
            assert chat.status_code == 200
            assert "respaldada por Revisora Local" in chat.text
    finally:
        embedder.close()
        engine.dispose()
