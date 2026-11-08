"""Pruebas de la reconciliación de arranque."""

from pathlib import Path

import pytest

from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import (
    Case,
    Conversation,
    Document,
    DocumentVersion,
    IngestionJob,
    Message,
    Run,
    new_id,
)
from secguard_advisor.db.recovery import reconcile_startup


@pytest.fixture
def session(tmp_path: Path):
    engine = create_engine_for_url(f"sqlite:///{tmp_path / 'recovery.sqlite3'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as db_session:
        yield db_session
    engine.dispose()


def _seed_open_operations(session) -> tuple[Case, Conversation, Run, IngestionJob]:
    case = Case(title="Caso", synthetic_notice="Escenario educativo sintético")
    session.add(case)
    session.flush()
    conversation = Conversation(case_id=case.id, thread_id=new_id())
    session.add(conversation)
    session.flush()
    question = Message(
        conversation_id=conversation.id,
        seq=1,
        role="user",
        content="pregunta",
        status="complete",
    )
    session.add(question)
    session.flush()
    run = Run(
        case_id=case.id,
        conversation_id=conversation.id,
        question_message_id=question.id,
        generator_model="qwen3.5:9b",
        generator_num_ctx=8192,
        generator_temperature=0.1,
        embedding_model="embeddinggemma",
        embedding_dim=768,
        prompt_version="chat-v1",
    )
    session.add(run)
    document = Document(
        scope_key=f"case:{case.id}",
        case_id=case.id,
        origin="case_evidence",
        title="Documento",
    )
    session.add(document)
    session.flush()
    version = DocumentVersion(
        document_id=document.id,
        scope_key=document.scope_key,
        version_number=1,
        original_filename="doc.pdf",
        content_type="application/pdf",
        size_bytes=10,
        sha256="a" * 64,
        status="processing",
        extraction_version="pypdf-7",
        normalization_version="norm-1",
        chunking_version="chunk-1",
    )
    session.add(version)
    session.flush()
    job = IngestionJob(
        case_id=case.id,
        version_id=version.id,
        status="running",
        attempts=1,
    )
    session.add(job)
    session.commit()
    return case, conversation, run, job


def test_recovery_marks_open_operations(session) -> None:
    case, conversation, run, job = _seed_open_operations(session)

    report = reconcile_startup(session)

    assert report.runs == 1
    assert report.ingestion_jobs == 1
    assert report.document_versions == 1
    assert session.get(Run, run.id).status == "interrupted"
    assert session.get(Run, run.id).finished_at is not None
    assert session.get(IngestionJob, job.id).status == "interrupted"
    assert session.get(IngestionJob, job.id).finished_at is not None

    version = session.query(DocumentVersion).one()
    assert version.status == "failed"
    assert version.error_code == "interrupted"

    question = Message(
        conversation_id=conversation.id,
        seq=2,
        role="user",
        content="otra pregunta",
        status="complete",
    )
    session.add(question)
    session.flush()
    session.add(
        Run(
            case_id=case.id,
            conversation_id=conversation.id,
            question_message_id=question.id,
            generator_model="qwen3.5:9b",
            generator_num_ctx=8192,
            generator_temperature=0.1,
            embedding_model="embeddinggemma",
            embedding_dim=768,
            prompt_version="chat-v1",
        )
    )
    session.commit()


def test_recovery_is_idempotent(session) -> None:
    _seed_open_operations(session)
    reconcile_startup(session)

    report = reconcile_startup(session)

    assert report.runs == 0
    assert report.ingestion_jobs == 0
    assert report.document_versions == 0
