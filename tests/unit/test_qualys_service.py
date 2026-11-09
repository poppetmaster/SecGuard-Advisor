"""Pruebas de staging, confirmación, cancelación y expiración Qualys."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import Case, QualysImportIssue
from secguard_advisor.vulnerabilities.service import (
    ImportNotFoundError,
    InvalidTransitionError,
    QualysImportService,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


@pytest.fixture
def service(tmp_path: Path):
    engine = create_engine_for_url(f"sqlite:///{tmp_path / 'qualys.sqlite3'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        case = Case(title="Caso Qualys", synthetic_notice="Escenario educativo sintético")
        session.add(case)
        session.commit()
        case_id = case.id
    settings = Settings(_env_file=None, storage_dir=tmp_path)
    yield QualysImportService(factory, settings), factory, case_id
    engine.dispose()


def _content(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_stage_confirm_and_idempotency(service) -> None:
    svc, _factory, case_id = service
    result = svc.stage_import(
        case_id,
        "qualys_synthetic_valid.csv",
        _content("qualys_synthetic_valid.csv"),
        manifest_path=FIXTURES / "qualys_synthetic_manifest.json",
    )
    assert result.import_record.status == "staged"
    assert result.import_record.manifest_status == "matched"
    assert result.import_record.row_count == 5
    assert len(svc.list_rows(case_id, result.import_record.id)) == 5

    confirmed = svc.confirm_import(case_id, result.import_record.id)
    assert confirmed.import_record.status == "confirmed"
    assert confirmed.import_record.confirmed_sequence == 1
    assert len(svc.list_rows(case_id, result.import_record.id)) == 5

    again = svc.stage_import(
        case_id,
        "qualys_synthetic_valid.csv",
        _content("qualys_synthetic_valid.csv"),
    )
    assert again.idempotent is True
    assert again.import_record.id == result.import_record.id
    assert svc.confirm_import(case_id, result.import_record.id).idempotent is True
    assert len(svc.list_rows(case_id, result.import_record.id)) == 5


def test_rejected_and_empty_files_do_not_store_rows(service) -> None:
    svc, factory, case_id = service
    rejected = svc.stage_import(
        case_id,
        "invalid_rows.csv",
        _content("qualys_synthetic_invalid_rows.csv"),
    )
    assert rejected.import_record.status == "rejected"
    assert rejected.import_record.error_code == "invalid_severity"
    assert svc.list_rows(case_id, rejected.import_record.id) == []

    empty = svc.stage_import(case_id, "empty.csv", _content("qualys_synthetic_empty.csv"))
    assert empty.import_record.status == "rejected"
    assert empty.import_record.csv_bytes == 0
    assert empty.import_record.error_code == "empty_file"
    assert svc.list_rows(case_id, empty.import_record.id) == []
    with factory() as session:
        issues = list(
            session.scalars(
                select(QualysImportIssue).where(
                    QualysImportIssue.import_id == empty.import_record.id
                )
            )
        )
    assert any(issue.code == "empty_file" for issue in issues)


def test_second_file_creates_independent_snapshot(service) -> None:
    svc, factory, case_id = service
    first = svc.stage_import(case_id, "first.csv", _content("qualys_synthetic_valid.csv"))
    svc.confirm_import(case_id, first.import_record.id)
    second = svc.stage_import(case_id, "second.csv", _content("qualys_synthetic_second.csv"))
    confirmed = svc.confirm_import(case_id, second.import_record.id)
    assert confirmed.import_record.confirmed_sequence == 2
    assert len(svc.list_rows(case_id, first.import_record.id)) == 5
    assert len(svc.list_rows(case_id, second.import_record.id)) == 2
    with factory() as session:
        first_record = session.get(type(first.import_record), first.import_record.id)
        second_record = session.get(type(second.import_record), second.import_record.id)
        assert first_record.status == "confirmed"
        assert second_record.status == "confirmed"


def test_cancel_and_expire_clean_rows(service) -> None:
    svc, factory, case_id = service
    staged = svc.stage_import(case_id, "cancel.csv", _content("qualys_synthetic_valid.csv"))
    assert len(svc.list_rows(case_id, staged.import_record.id)) == 5
    cancelled = svc.cancel_import(case_id, staged.import_record.id)
    assert cancelled.status == "cancelled"
    assert svc.list_rows(case_id, staged.import_record.id) == []

    expiring = svc.stage_import(case_id, "expire.csv", _content("qualys_synthetic_mixed.csv"))
    future = datetime.now(UTC) + timedelta(days=2)
    assert svc.expire_stale(now=future) >= 1
    with factory() as session:
        record = session.get(type(expiring.import_record), expiring.import_record.id)
        assert record.status == "expired"
    assert svc.list_rows(case_id, expiring.import_record.id) == []


def test_manifest_mismatch_rejects(service, tmp_path: Path) -> None:
    svc, _factory, case_id = service
    payload = json.loads((FIXTURES / "qualys_synthetic_manifest.json").read_text(encoding="utf-8"))
    payload["output_bytes"] += 1
    manifest = tmp_path / "mismatch.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    result = svc.stage_import(
        case_id,
        "mismatch.csv",
        _content("qualys_synthetic_valid.csv"),
        manifest_path=manifest,
    )
    assert result.import_record.status == "rejected"
    assert result.import_record.manifest_status == "mismatch"
    assert result.import_record.error_code == "manifest_mismatch"
    assert svc.list_rows(case_id, result.import_record.id) == []


def test_confirm_rejected_raises_and_case_isolation(service) -> None:
    svc, factory, case_id = service
    rejected = svc.stage_import(case_id, "bad.csv", _content("qualys_synthetic_invalid_rows.csv"))
    with pytest.raises(InvalidTransitionError):
        svc.confirm_import(case_id, rejected.import_record.id)
    with factory() as session:
        other = Case(title="Otro caso", synthetic_notice="Escenario educativo sintético")
        session.add(other)
        session.commit()
        other_id = other.id
    with pytest.raises(ImportNotFoundError):
        svc.get_import(other_id, rejected.import_record.id)
    other_import = svc.stage_import(other_id, "x.csv", _content("qualys_synthetic_valid.csv"))
    assert other_import.import_record.case_id == other_id
    with pytest.raises(ImportNotFoundError):
        svc.get_import(case_id, other_import.import_record.id)
