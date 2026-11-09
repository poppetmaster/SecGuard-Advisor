"""Pruebas de las restricciones e invariantes del esquema."""

from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import (
    Asset,
    Case,
    Conversation,
    Document,
    DocumentChunk,
    DocumentVersion,
    Finding,
    Message,
    MessageCitation,
    Run,
    SyntheticDataset,
    new_id,
)

EXPECTED_TABLES = {
    "assets",
    "cases",
    "conversations",
    "document_chunks",
    "document_versions",
    "documents",
    "finding_cves",
    "findings",
    "ingestion_jobs",
    "message_citations",
    "messages",
    "run_sources",
    "run_steps",
    "run_tool_calls",
    "runs",
    "synthetic_datasets",
    "qualys_import_issues",
    "qualys_imports",
    "qualys_vulnerabilities",
    "qualys_vulnerability_cves",
}


@pytest.fixture
def session(tmp_path: Path):
    engine = create_engine_for_url(f"sqlite:///{tmp_path / 'schema.sqlite3'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as db_session:
        yield db_session
    engine.dispose()


def _case(session, title: str = "Caso de prueba") -> Case:
    case = Case(title=title, synthetic_notice="Escenario educativo sintético")
    session.add(case)
    session.flush()
    return case


def _conversation(session, case: Case) -> Conversation:
    conversation = Conversation(case_id=case.id, thread_id=new_id())
    session.add(conversation)
    session.flush()
    return conversation


def _message(session, conversation: Conversation, seq: int = 1) -> Message:
    message = Message(
        conversation_id=conversation.id,
        seq=seq,
        role="user",
        content="pregunta",
        status="complete",
    )
    session.add(message)
    session.flush()
    return message


def _run(session, case: Case, conversation: Conversation, question: Message) -> Run:
    return Run(
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


def _document(session, case: Case) -> Document:
    document = Document(
        scope_key=f"case:{case.id}",
        case_id=case.id,
        origin="case_evidence",
        title="Documento de prueba",
    )
    session.add(document)
    session.flush()
    return document


def _version(session, document: Document, sha: str = "a" * 64) -> DocumentVersion:
    version = DocumentVersion(
        document_id=document.id,
        scope_key=document.scope_key,
        version_number=1,
        original_filename="doc.pdf",
        content_type="application/pdf",
        size_bytes=10,
        sha256=sha,
        status="pending",
        extraction_version="pypdf-7",
        normalization_version="norm-1",
        chunking_version="chunk-1",
    )
    session.add(version)
    session.flush()
    return version


def _chunk(session, version: DocumentVersion) -> DocumentChunk:
    chunk = DocumentChunk(
        version_id=version.id,
        chunk_index=0,
        char_start=0,
        char_end=5,
        text="texto",
        text_sha256="b" * 64,
        token_count=2,
        token_count_source="ollama_prompt_eval_count_single",
        embedding_model="embeddinggemma",
        embedding_dim=768,
        index_status="indexed",
        locator="p:1",
    )
    session.add(chunk)
    session.flush()
    return chunk


def test_creates_the_expected_tables(session) -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_only_one_running_run_per_case(session) -> None:
    case = _case(session)
    conversation = _conversation(session, case)
    first_question = _message(session, conversation, seq=1)
    second_question = _message(session, conversation, seq=2)

    session.add(_run(session, case, conversation, first_question))
    session.commit()

    session.add(_run(session, case, conversation, second_question))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_content_cannot_repeat_within_scope(session) -> None:
    case = _case(session)
    document = _document(session, case)
    _version(session, document)
    session.commit()

    duplicate = DocumentVersion(
        document_id=document.id,
        scope_key=document.scope_key,
        version_number=2,
        original_filename="copia.pdf",
        content_type="application/pdf",
        size_bytes=10,
        sha256="a" * 64,
        status="pending",
        extraction_version="pypdf-7",
        normalization_version="norm-1",
        chunking_version="chunk-1",
    )
    session.add(duplicate)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_public_document_cannot_belong_to_a_case(session) -> None:
    case = _case(session)
    document = Document(
        scope_key="public:csf2",
        case_id=case.id,
        origin="public_corpus",
        source_id="csf2",
        title="CSF",
    )
    session.add(document)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_review_requires_author_and_date(session) -> None:
    case = _case(session)
    conversation = _conversation(session, case)
    question = _message(session, conversation)
    run = _run(session, case, conversation, question)
    session.add(run)
    session.flush()
    answer = Message(
        conversation_id=conversation.id,
        seq=2,
        role="assistant",
        content="respuesta",
        status="complete",
    )
    session.add(answer)
    session.flush()
    document = _document(session, case)
    version = _version(session, document)
    chunk = _chunk(session, version)

    citation = MessageCitation(
        message_id=answer.id,
        chunk_id=chunk.id,
        document_id=document.id,
        document_version_id=version.id,
        quote="texto",
        locator="p:1",
        check_status="valid",
        support_review_status="supported",
    )
    session.add(citation)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_attempt_is_unique_per_question(session) -> None:
    case = _case(session)
    conversation = _conversation(session, case)
    question = _message(session, conversation)

    session.add(_run(session, case, conversation, question))
    session.commit()

    duplicate = _run(session, case, conversation, question)
    session.add(duplicate)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_finding_severity_is_validated(session) -> None:
    case = _case(session)
    asset = Asset(case_id=case.id, name="api-gateway")
    dataset = SyntheticDataset(
        name="demo-findings",
        version="1",
        seed=42,
        checksum="c" * 64,
        applies_to_case_id=case.id,
        description="Datos sintéticos",
    )
    session.add_all([asset, dataset])
    session.flush()

    finding = Finding(
        case_id=case.id,
        asset_id=asset.id,
        dataset_id=dataset.id,
        title="Hallazgo",
        severity_raw="5",
        severity_label="Urgent",
        provenance="synthetic:demo-findings",
    )
    session.add(finding)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()
