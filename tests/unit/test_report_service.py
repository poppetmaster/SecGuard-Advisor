"""Immutable report versions and artifact persistence."""

import pytest
from sqlalchemy import select
from tests.fixtures.report_fixtures import _snapshot, default_rows

from secguard_advisor.conversation.concurrency import GenerationSlot
from secguard_advisor.db.models import Case, ReportArtifact, ReportVersion
from secguard_advisor.reports.errors import ReportError
from secguard_advisor.reports.service import create_report_version, get_version, list_versions


def _fake_charts(_settings, charts):
    return {key: f"<svg>{key}</svg>" for key in charts}


def _fake_pdf(_settings, _html, path):
    content = b"%PDF-1.4\n% fictional\n%%EOF\n"
    path.write_bytes(content)
    return content


def test_versions_are_immutable_and_increment(report_context) -> None:
    with report_context.session_factory() as session:
        first = create_report_version(
            session,
            report_context.settings,
            case_id=report_context.case_id,
            snapshot_id=report_context.snapshot_id,
            author="Prueba",
            synthesize=False,
            chart_renderer=_fake_charts,
            pdf_renderer=_fake_pdf,
        )
        session.commit()
        second = create_report_version(
            session,
            report_context.settings,
            case_id=report_context.case_id,
            snapshot_id=report_context.snapshot_id,
            author="Prueba",
            synthesize=False,
            chart_renderer=_fake_charts,
            pdf_renderer=_fake_pdf,
        )
        session.commit()
        versions = list_versions(session, report_context.case_id)
        assert first.version_number == 1
        assert second.version_number == 2
        assert len(versions) == 2
        stored = get_version(session, report_context.case_id, first.report_id, first.version_number)
        assert stored.dataset_sha256 == first.dataset_sha256
        assert stored.synthesis_status == "not_requested"


def test_generation_key_recovers_existing_version(report_context) -> None:
    with report_context.session_factory() as session:
        first = create_report_version(
            session,
            report_context.settings,
            case_id=report_context.case_id,
            snapshot_id=report_context.snapshot_id,
            author="Prueba",
            generation_key="auto:test-evaluation",
            synthesize=False,
            chart_renderer=_fake_charts,
            pdf_renderer=_fake_pdf,
        )
        session.commit()
        recovered = create_report_version(
            session,
            report_context.settings,
            case_id=report_context.case_id,
            snapshot_id=report_context.snapshot_id,
            author="Prueba",
            generation_key="auto:test-evaluation",
            synthesize=False,
            chart_renderer=_fake_charts,
            pdf_renderer=_fake_pdf,
        )
        session.commit()
        assert recovered.version_id == first.version_id
        assert session.query(ReportVersion).count() == 1


def test_partial_artifact_failure_is_cleaned_and_retried(report_context, monkeypatch) -> None:
    import secguard_advisor.reports.service as service

    with report_context.session_factory() as session:
        first = create_report_version(
            session,
            report_context.settings,
            case_id=report_context.case_id,
            snapshot_id=report_context.snapshot_id,
            author="Primera",
            synthesize=False,
            chart_renderer=_fake_charts,
            pdf_renderer=_fake_pdf,
        )
        session.commit()
        first_pdf = session.scalar(
            select(ReportArtifact).where(
                ReportArtifact.report_version_id == first.version_id,
                ReportArtifact.kind == "pdf",
            )
        )
        first_path = report_context.settings.reports_dir / first_pdf.relative_path
        first_bytes = first_path.read_bytes()

        original = service.write_artifact
        calls = {"count": 0}

        def flaky(settings, relative, content):
            calls["count"] += 1
            if calls["count"] == 2:
                raise OSError("fallo simulado de escritura")
            return original(settings, relative, content)

        monkeypatch.setattr(service, "write_artifact", flaky)
        with pytest.raises(OSError):
            create_report_version(
                session,
                report_context.settings,
                case_id=report_context.case_id,
                snapshot_id=report_context.snapshot_id,
                author="Segunda",
                generation_key="auto:retry-failure",
                synthesize=False,
                chart_renderer=_fake_charts,
                pdf_renderer=_fake_pdf,
            )
        session.rollback()
        failed = session.scalar(
            select(ReportVersion).where(ReportVersion.generation_key == "auto:retry-failure")
        )
        assert failed is not None and failed.status == "failed"

        monkeypatch.setattr(service, "write_artifact", original)
        retried = create_report_version(
            session,
            report_context.settings,
            case_id=report_context.case_id,
            snapshot_id=report_context.snapshot_id,
            author="Segunda",
            generation_key="auto:retry-failure",
            synthesize=False,
            chart_renderer=_fake_charts,
            pdf_renderer=_fake_pdf,
        )
        session.commit()
        assert retried.version_number == failed.version_number
        assert first_path.read_bytes() == first_bytes
        assert session.query(ReportVersion).filter(ReportVersion.status == "ready").count() == 2


def test_generation_slot_prevents_concurrent_generation(report_context) -> None:
    slot = GenerationSlot(0.01)
    assert slot.acquire()
    try:
        with (
            report_context.session_factory() as session,
            pytest.raises(ReportError) as error,
        ):
            create_report_version(
                session,
                report_context.settings,
                case_id=report_context.case_id,
                snapshot_id=report_context.snapshot_id,
                author="Concurrente",
                synthesize=False,
                chart_renderer=_fake_charts,
                pdf_renderer=_fake_pdf,
                generation_slot=slot,
            )
        assert error.value.code == "generation_busy"
        assert error.value.status == 409
    finally:
        slot.release()


def test_generation_key_belongs_to_the_case(report_context) -> None:
    with report_context.session_factory() as session:
        first = create_report_version(
            session,
            report_context.settings,
            case_id=report_context.case_id,
            snapshot_id=report_context.snapshot_id,
            author="Caso A",
            generation_key="auto:case-a",
            synthesize=False,
            chart_renderer=_fake_charts,
            pdf_renderer=_fake_pdf,
        )
        session.commit()
        other = Case(title="Caso B", synthetic_notice="Sintético")
        session.add(other)
        session.flush()
        other_snapshot = _snapshot(session, other.id, default_rows())
        session.commit()
        with pytest.raises(ReportError) as error:
            create_report_version(
                session,
                report_context.settings,
                case_id=other.id,
                snapshot_id=other_snapshot.id,
                author="Caso B",
                generation_key="auto:case-a",
                synthesize=False,
                chart_renderer=_fake_charts,
                pdf_renderer=_fake_pdf,
            )
        assert error.value.code == "generation_key_conflict"
        assert first.version_id
