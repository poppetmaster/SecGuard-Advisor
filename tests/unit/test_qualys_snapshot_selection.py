"""Pruebas de snapshots históricos y fijación por turno."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.conversation.context import TurnContext, TurnDependencies
from secguard_advisor.conversation.nodes import tools
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import Case
from secguard_advisor.tools.findings import FindingsQuery, ToolArgumentError
from secguard_advisor.vulnerabilities.service import QualysImportService

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


@pytest.fixture
def snapshots_env(tmp_path: Path):
    engine = create_engine_for_url(f"sqlite:///{tmp_path / 'snapshots.sqlite3'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        case = Case(title="Caso snapshots", synthetic_notice="Escenario educativo sintético")
        session.add(case)
        session.commit()
        case_id = case.id
    settings = Settings(_env_file=None, storage_dir=tmp_path)
    service = QualysImportService(factory, settings)
    first = service.stage_import(
        case_id,
        "first.csv",
        (FIXTURES / "qualys_synthetic_valid.csv").read_bytes(),
        manifest_path=FIXTURES / "qualys_synthetic_manifest.json",
    )
    service.confirm_import(case_id, first.import_record.id)
    second = service.stage_import(
        case_id,
        "second.csv",
        (FIXTURES / "qualys_synthetic_second.csv").read_bytes(),
    )
    service.confirm_import(case_id, second.import_record.id)
    yield factory, case_id, settings, service, first.import_record.id, second.import_record.id
    engine.dispose()


def _query(factory, case_id: str) -> FindingsQuery:
    return FindingsQuery(factory, CaseScope(case_id=case_id))


def test_latest_default_explicit_and_independent_counts(snapshots_env) -> None:
    factory, case_id, _settings, _service, first_id, second_id = snapshots_env
    query = _query(factory, case_id)

    default = query.execute({"origin": "imported", "detail": True})
    first = query.execute({"origin": "imported", "snapshot_id": first_id, "detail": True})

    assert default["snapshot"]["id"] == second_id
    assert default["snapshot"]["sequence"] == 2
    assert default["total"] == 2
    assert first["snapshot"]["id"] == first_id
    assert first["snapshot"]["sequence"] == 1
    assert first["total"] == 3
    assert default["total"] + first["total"] == 5
    assert default["snapshot"] != first["snapshot"]


def test_reimport_same_hash_is_idempotent_and_distinct_file_is_new(snapshots_env) -> None:
    _factory, case_id, _settings, service, first_id, second_id = snapshots_env
    again = service.stage_import(
        case_id,
        "first.csv",
        (FIXTURES / "qualys_synthetic_valid.csv").read_bytes(),
    )
    assert again.idempotent is True
    assert again.import_record.id == first_id
    confirmed = service.list_confirmed(case_id)
    assert [item.id for item in confirmed] == [second_id, first_id]


def test_fixed_snapshot_survives_concurrent_confirmation(snapshots_env) -> None:
    factory, case_id, _settings, service, first_id, _second_id = snapshots_env
    query = _query(factory, case_id)
    fixed = query.execute({"origin": "imported"}, fixed_snapshot_id=first_id)
    assert fixed["snapshot"]["id"] == first_id

    third = service.stage_import(
        case_id,
        "third.csv",
        (FIXTURES / "qualys_synthetic_mixed.csv").read_bytes(),
    )
    service.confirm_import(case_id, third.import_record.id)
    still_fixed = query.execute({"origin": "imported"}, fixed_snapshot_id=first_id)
    latest = query.execute({"origin": "imported"})
    assert still_fixed["snapshot"]["id"] == first_id
    assert latest["snapshot"]["id"] == third.import_record.id
    assert latest["snapshot"]["sequence"] == 3


def test_snapshot_locked_and_case_isolation(snapshots_env) -> None:
    factory, case_id, _settings, service, first_id, second_id = snapshots_env
    query = _query(factory, case_id)
    with pytest.raises(ToolArgumentError) as locked:
        query.execute(
            {"origin": "imported", "snapshot_id": first_id},
            fixed_snapshot_id=second_id,
        )
    assert locked.value.code == "snapshot_locked"

    with factory() as session:
        other = Case(title="Otro caso", synthetic_notice="Escenario educativo sintético")
        session.add(other)
        session.commit()
        other_id = other.id
    other_import = service.stage_import(
        other_id,
        "other.csv",
        (FIXTURES / "qualys_synthetic_valid.csv").read_bytes(),
    )
    with pytest.raises(ToolArgumentError) as staged_not_found:
        _query(factory, other_id).execute(
            {"origin": "imported", "snapshot_id": other_import.import_record.id}
        )
    assert staged_not_found.value.code == "snapshot_not_found"
    service.confirm_import(other_id, other_import.import_record.id)
    own = _query(factory, other_id).execute({"origin": "imported"})
    assert own["total"] == 3
    with pytest.raises(ToolArgumentError) as foreign:
        _query(factory, case_id).execute(
            {"origin": "imported", "snapshot_id": other_import.import_record.id}
        )
    assert foreign.value.code == "snapshot_not_found"


def test_turn_state_fixes_snapshot_and_new_turn_can_select_another(snapshots_env) -> None:
    factory, case_id, settings, service, first_id, second_id = snapshots_env

    def context() -> TurnContext:
        return TurnContext(
            factory=factory,
            deps=TurnDependencies(
                generator=object(),
                embedder=object(),
                index=object(),
                settings=settings,
                token_counter=object(),
            ),
            scope=CaseScope(case_id=case_id),
            conversation_id="conversation",
            question_message_id="question",
            run_id="run",
            attempt_no=1,
            question="¿Cuántos registros importados hay?",
            started_perf=time.perf_counter(),
            started_at="2026-11-09T00:00:00+00:00",
        )

    config = {"configurable": {"runtime": context()}}
    state = {
        "tool_results": (),
        "tool_records": (),
        "tool_calls": 0,
        "step_count": 0,
        "selected_import_id": None,
        "decision": {"arguments": {"origin": "imported"}},
    }
    first_step = tools(state, config)
    assert first_step["selected_import_id"] == second_id
    state.update(first_step)

    third = service.stage_import(
        case_id,
        "third.csv",
        (FIXTURES / "qualys_synthetic_mixed.csv").read_bytes(),
    )
    service.confirm_import(case_id, third.import_record.id)

    state["decision"] = {"arguments": {"origin": "imported"}}
    second_step = tools(state, config)
    assert second_step["selected_import_id"] == second_id
    assert second_step["tool_records"][-1].summary["snapshot"]["id"] == second_id

    state.update(second_step)
    state["decision"] = {"arguments": {"origin": "imported", "snapshot_id": first_id}}
    locked_step = tools(state, config)
    assert locked_step["selected_import_id"] == second_id
    assert locked_step["tool_records"][-1].status == "invalid_arguments"
    assert locked_step["tool_records"][-1].error_code == "snapshot_locked"

    new_state = {
        "tool_results": (),
        "tool_records": (),
        "tool_calls": 0,
        "step_count": 0,
        "selected_import_id": None,
        "decision": {"arguments": {"origin": "imported", "snapshot_id": first_id}},
    }
    new_turn = tools(new_state, {"configurable": {"runtime": context()}})
    assert new_turn["selected_import_id"] == first_id
    assert new_turn["tool_records"][-1].summary["snapshot"]["sequence"] == 1
