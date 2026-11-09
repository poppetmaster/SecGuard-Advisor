"""Estados, intentos y serialización de la evidencia de ejecución."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import select

from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import (
    Case,
    Conversation,
    Document,
    DocumentChunk,
    DocumentVersion,
    Message,
    Run,
    RunSource,
    RunStep,
    RunToolCall,
    new_id,
)
from secguard_advisor.evidence.runs import (
    ActiveRunConflict,
    close_run,
    create_run,
    record_trace,
    serialize_attempts,
    serialize_sources,
    serialize_steps,
    serialize_tool_calls,
)


@pytest.fixture
def factory(tmp_path: Path):
    engine = create_engine_for_url(f"sqlite:///{tmp_path / 'runs.sqlite3'}")
    Base.metadata.create_all(engine)
    yield create_session_factory(engine)
    engine.dispose()


def _context(session):
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
    return case, conversation, question


def _create(session, case, conversation, question, attempt_no: int = 1, retry_of=None) -> Run:
    return create_run(
        session,
        case_id=case.id,
        conversation_id=conversation.id,
        question_message_id=question.id,
        generator_model="qwen3.5:9b",
        generator_num_ctx=8192,
        generator_temperature=0.1,
        embedding_model="embeddinggemma",
        embedding_dim=768,
        prompt_version="chat-v4",
        attempt_no=attempt_no,
        retry_of_run_id=retry_of,
    )


def test_attempts_are_linked_without_duplicating_the_question(factory) -> None:
    with factory() as session:
        case, conversation, question = _context(session)
        first = _create(session, case, conversation, question)
        session.commit()
        close_run(session, first, status="failed", outcome="error", error_code="model_unavailable")
        session.commit()

        second = _create(session, case, conversation, question, attempt_no=2, retry_of=first.id)
        session.commit()
        close_run(session, second, status="succeeded", outcome="answered", duration_ms=12)
        session.commit()

        attempts = serialize_attempts(session, second)

    assert [item["attempt_no"] for item in attempts] == [1, 2]
    assert attempts[0]["id"] == first.id
    assert attempts[1]["id"] == second.id
    assert attempts[0]["is_current"] is False
    assert attempts[1]["is_current"] is True
    assert attempts[1]["retry_of_run_id"] == first.id
    assert attempts[0]["status"] == "failed"
    assert attempts[1]["status"] == "succeeded"


def test_one_active_run_per_case_is_enforced(factory) -> None:
    with factory() as session:
        case, conversation, question = _context(session)
        _create(session, case, conversation, question)
        session.commit()

        other = Message(
            conversation_id=conversation.id,
            seq=2,
            role="user",
            content="otra",
            status="complete",
        )
        session.add(other)
        session.flush()

        with pytest.raises(ActiveRunConflict):
            _create(session, case, conversation, other)


def test_application_never_writes_confirmed(factory) -> None:
    with factory() as session:
        case, conversation, question = _context(session)
        run = _create(session, case, conversation, question)
        session.commit()

        with pytest.raises(ValueError):
            record_trace(
                factory,
                run.id,
                status="confirmed",
                trace_id="trace-1",
            )

        stored = session.get(Run, run.id)
        assert stored.trace_status == "disabled"
        assert stored.trace_id is None


def test_record_trace_accepts_submitted_and_failed(factory) -> None:
    with factory() as session:
        case, conversation, question = _context(session)
        run = _create(session, case, conversation, question)
        session.commit()

    record_trace(
        factory,
        run.id,
        status="submitted",
        trace_id="trace-1",
        trace_url="https://example.test/trace-1",
    )
    with factory() as session:
        stored = session.get(Run, run.id)
        assert stored.trace_status == "submitted"
        assert stored.trace_id == "trace-1"
        assert stored.trace_url == "https://example.test/trace-1"

    record_trace(factory, run.id, status="failed")
    with factory() as session:
        stored = session.get(Run, run.id)
        assert stored.trace_status == "failed"


def test_steps_sources_and_tools_are_serialized_without_inventing_values(factory) -> None:
    with factory() as session:
        case, conversation, question = _context(session)
        run = _create(session, case, conversation, question)
        session.flush()
        session.add(
            RunStep(
                run_id=run.id,
                seq=1,
                name="decide",
                origin="model",
                status="ok",
                duration_ms=15,
                detail_json=json.dumps({"use_findings": True, "admitted_tokens": 190}),
            )
        )
        session.add(
            RunStep(
                run_id=run.id,
                seq=2,
                name="tools",
                origin="deterministic",
                status="ok",
                duration_ms=None,
                detail_json=None,
            )
        )
        document = Document(
            scope_key=f"case:{case.id}",
            case_id=case.id,
            origin="case_evidence",
            title="Política interna",
        )
        session.add(document)
        session.flush()
        version = DocumentVersion(
            document_id=document.id,
            scope_key=document.scope_key,
            version_number=1,
            original_filename="politica.md",
            content_type="text/markdown",
            size_bytes=10,
            sha256="0" * 64,
            status="available",
            extraction_version="v1",
            normalization_version="v1",
            chunking_version="v1",
        )
        session.add(version)
        session.flush()
        chunk = DocumentChunk(
            version_id=version.id,
            chunk_index=0,
            char_start=0,
            char_end=10,
            text="contenido",
            text_sha256="0" * 64,
            token_count=1,
            token_count_source="test",
            embedding_model="fake",
            embedding_dim=4,
            index_status="indexed",
            locator="/x",
        )
        session.add(chunk)
        session.flush()
        session.add(
            RunSource(
                run_id=run.id,
                chunk_id=chunk.id,
                origin="case_evidence",
                rank=1,
                score=0.81,
                used_in_answer=False,
            )
        )
        session.add(
            RunToolCall(
                run_id=run.id,
                seq=1,
                tool_name="findings_query",
                origin="model_requested",
                arguments_json=json.dumps({"severity": "High"}),
                result_summary_json=None,
                status="invalid_arguments",
                error_code="invalid_severity",
                duration_ms=2,
            )
        )
        session.commit()

        steps = serialize_steps(session, run.id)
        sources = serialize_sources(session, run.id)
        tools = serialize_tool_calls(session, run.id)

    assert steps[0] == {
        "seq": 1,
        "name": "decide",
        "origin": "model",
        "status": "ok",
        "duration_ms": 15,
        "detail": {"use_findings": True, "admitted_tokens": 190},
    }
    assert steps[1]["duration_ms"] is None
    assert steps[1]["detail"] is None
    assert sources[0]["title"] == "Política interna"
    assert sources[0]["page"] is None
    assert sources[0]["used_in_answer"] is False
    assert tools[0]["summary"] is None
    assert tools[0]["arguments"] == {"severity": "High"}
    assert tools[0]["status"] == "invalid_arguments"
    assert tools[0]["detail_items"] is None
    assert tools[0]["detail_source"] is None


def test_serialize_attempts_returns_empty_for_a_missing_question(factory) -> None:
    with factory() as session:
        case, conversation, _question = _context(session)
        orphan = Run(
            case_id=case.id,
            conversation_id=conversation.id,
            question_message_id=None,
            generator_model="qwen3.5:9b",
            generator_num_ctx=8192,
            generator_temperature=0.1,
            embedding_model="embeddinggemma",
            embedding_dim=768,
            prompt_version="chat-v4",
        )
        session.add(orphan)
        session.commit()

        assert serialize_attempts(session, orphan) == []


def test_trace_url_column_round_trips(factory) -> None:
    with factory() as session:
        case, conversation, question = _context(session)
        run = _create(session, case, conversation, question)
        run.trace_url = "https://example.test/run"
        session.commit()
        assert session.scalar(select(Run.trace_url).where(Run.id == run.id)) == (
            "https://example.test/run"
        )
