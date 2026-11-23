"""Immutable report versions and artifact persistence."""

from secguard_advisor.db.models import ReportVersion
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
