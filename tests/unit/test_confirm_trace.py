"""Confirmación de trazas: solo actualiza tras verificar por API de lectura."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import Case, Conversation, Message, Run
from secguard_advisor.evidence.confirm import ConfirmationError, confirm_trace
from secguard_advisor.evidence.runs import create_run

TRACE_ID = "01a1bee1-9f32-7561-8809-e653707d28d8"
PROJECT_ID = "2f60af7f-6479-4fbb-8328-5feabf207060"


class FakeProject:
    id = PROJECT_ID


class FakeRemote:
    def __init__(self, *, run_id: str, case_id: str, attempt_no: int = 1) -> None:
        self.id = TRACE_ID
        self.session_id = PROJECT_ID
        self.name = "secguard-advisor.turn"
        self.start_time = datetime(2026, 11, 9, 5, 56, 59, tzinfo=UTC)
        self.inputs = {
            "run_id": run_id,
            "case_id": case_id,
            "attempt_no": attempt_no,
            "prompt_version": "chat-v4",
        }


class FakeClient:
    def __init__(self, remote=None, *, error: Exception | None = None) -> None:
        self.remote = remote
        self.error = error

    def read_run(self, _trace_id):
        if self.error is not None:
            raise self.error
        return self.remote

    def read_project(self, *, project_name):
        assert project_name == "secguard-advisor-dev"
        return FakeProject()

    def _construct_run_url(self, **_kwargs):
        return f"https://smith.test/trace/{TRACE_ID}"


def _settings(tmp_path: Path, **overrides) -> Settings:
    values = {
        "langsmith_tracing": True,
        "langsmith_api_key": "lsv2_decoy_key",
        "langsmith_project": "secguard-advisor-dev",
        "langsmith_endpoint": "https://api.smith.test",
    }
    values.update(overrides)
    return Settings(_env_file=None, storage_dir=tmp_path / "storage", **values)


@pytest.fixture
def env(tmp_path: Path):
    settings = _settings(tmp_path)
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        case = Case(title="Caso", synthetic_notice="Escenario educativo")
        session.add(case)
        session.flush()
        conversation = Conversation(case_id=case.id, thread_id="thread")
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
        run = create_run(
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
        )
        run.trace_status = "submitted"
        run.trace_id = TRACE_ID
        run.trace_url = "https://smith.test/original"
        session.commit()
        yield settings, factory, run.id, case.id, run.attempt_no
    engine.dispose()


def test_confirmation_persists_identity_date_and_evidence(env) -> None:
    settings, factory, run_id, case_id, attempt_no = env
    client = FakeClient(FakeRemote(run_id=run_id, case_id=case_id, attempt_no=attempt_no))

    result = confirm_trace(
        factory,
        settings,
        run_id=run_id,
        trace_id=TRACE_ID,
        reviewer="Revisora de prueba",
        client_factory=lambda **_kwargs: client,
    )

    assert result.status == "confirmed"
    assert result.reviewer == "Revisora de prueba"
    with factory() as session:
        run = session.get(Run, run_id)
        assert run.trace_status == "confirmed"
        assert run.trace_confirmed_by == "Revisora de prueba"
        assert run.trace_confirmed_at
        assert TRACE_ID in (run.trace_evidence_json or "")
        assert run.trace_url == f"https://smith.test/trace/{TRACE_ID}"


def test_confirmation_is_idempotent_for_the_same_trace(env) -> None:
    settings, factory, run_id, case_id, attempt_no = env
    client = FakeClient(FakeRemote(run_id=run_id, case_id=case_id, attempt_no=attempt_no))
    kwargs = {
        "run_id": run_id,
        "trace_id": TRACE_ID,
        "reviewer": "Revisora de prueba",
        "client_factory": lambda **_kwargs: client,
    }

    confirm_trace(factory, settings, **kwargs)
    second = confirm_trace(factory, settings, **kwargs)

    assert second.status == "already_confirmed"


def test_missing_reviewer_is_rejected_without_changes(env) -> None:
    settings, factory, run_id, _case_id, _attempt_no = env

    with pytest.raises(ConfirmationError) as captured:
        confirm_trace(
            factory,
            settings,
            run_id=run_id,
            trace_id=TRACE_ID,
            reviewer="  ",
            client_factory=lambda **_kwargs: FakeClient(),
        )

    assert captured.value.code == "reviewer_required"
    with factory() as session:
        assert session.get(Run, run_id).trace_status == "submitted"


def test_trace_from_another_run_is_rejected(env) -> None:
    settings, factory, run_id, case_id, _attempt_no = env
    client = FakeClient(FakeRemote(run_id="otra-ejecucion", case_id=case_id))

    with pytest.raises(ConfirmationError) as captured:
        confirm_trace(
            factory,
            settings,
            run_id=run_id,
            trace_id=TRACE_ID,
            reviewer="Revisora",
            client_factory=lambda **_kwargs: client,
        )

    assert captured.value.code == "trace_not_linked"
    with factory() as session:
        assert session.get(Run, run_id).trace_status == "submitted"


def test_trace_from_another_project_is_rejected(env) -> None:
    settings, factory, run_id, case_id, attempt_no = env
    remote = FakeRemote(run_id=run_id, case_id=case_id, attempt_no=attempt_no)
    remote.session_id = "otro-proyecto"

    with pytest.raises(ConfirmationError) as captured:
        confirm_trace(
            factory,
            settings,
            run_id=run_id,
            trace_id=TRACE_ID,
            reviewer="Revisora",
            client_factory=lambda **_kwargs: FakeClient(remote),
        )

    assert captured.value.code == "project_mismatch"


def test_api_error_leaves_the_run_unchanged(env) -> None:
    settings, factory, run_id, _case_id, _attempt_no = env

    with pytest.raises(ConfirmationError) as captured:
        confirm_trace(
            factory,
            settings,
            run_id=run_id,
            trace_id=TRACE_ID,
            reviewer="Revisora",
            client_factory=lambda **_kwargs: FakeClient(error=RuntimeError("caído")),
        )

    assert captured.value.code == "api_unavailable"
    with factory() as session:
        assert session.get(Run, run_id).trace_status == "submitted"


def test_disabled_trace_cannot_be_confirmed(env) -> None:
    settings, factory, run_id, _case_id, _attempt_no = env
    with factory() as session:
        run = session.get(Run, run_id)
        run.trace_status = "disabled"
        run.trace_id = None
        session.commit()

    with pytest.raises(ConfirmationError) as captured:
        confirm_trace(
            factory,
            settings,
            run_id=run_id,
            trace_id=TRACE_ID,
            reviewer="Revisora",
            client_factory=lambda **_kwargs: FakeClient(),
        )

    assert captured.value.code == "trace_not_submitted"
