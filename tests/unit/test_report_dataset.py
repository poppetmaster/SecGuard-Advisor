"""Canonical dataset immutability and validity."""

from secguard_advisor.db.models import Case, QualysImport
from secguard_advisor.reports.dataset import build_dataset
from secguard_advisor.reports.errors import ReportError


def test_dataset_hash_is_stable(report_context) -> None:
    with report_context.session_factory() as session:
        case = session.get(Case, report_context.case_id)
        snapshot = session.get(QualysImport, report_context.snapshot_id)
        first, hash_one = build_dataset(session, case=case, snapshot=snapshot)
        second, hash_two = build_dataset(session, case=case, snapshot=snapshot)
    assert first == second
    assert hash_one == hash_two
    assert first["assets_top"]["items"][0]["alias"] == "Activo 01"
    assert first["snapshot"]["import_id"] == report_context.snapshot_id


def test_dataset_rejects_foreign_or_unconfirmed_snapshot(report_context) -> None:
    with report_context.session_factory() as session:
        case = session.get(Case, report_context.case_id)
        snapshot = session.get(QualysImport, report_context.snapshot_id)
        snapshot.status = "staged"
        try:
            build_dataset(session, case=case, snapshot=snapshot)
        except ReportError as exc:
            assert exc.code == "snapshot_not_confirmed"
        else:  # pragma: no cover
            raise AssertionError("El snapshot no confirmado debía rechazarse")
