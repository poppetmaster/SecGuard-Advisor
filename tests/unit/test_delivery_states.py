"""Event and component state transitions."""

from __future__ import annotations

from tests.fixtures.notifications import create_ready_report, make_eligible_contact

from secguard_advisor.db.models import ReportVersion
from secguard_advisor.notifications.delivery import components, ensure_event, refresh_event_status
from secguard_advisor.notifications.manifest import build_manifest


def test_event_states_follow_components(report_context) -> None:
    result = create_ready_report(report_context)
    contact, _ = make_eligible_contact(report_context)
    with report_context.session_factory() as session:
        version = session.get(ReportVersion, result.version_id)
        manifest = build_manifest(session, version, [contact.id])
        event, _ = ensure_event(
            session, version=version, contact=contact, manifest=manifest, mode="manual"
        )
        values = components(session, event.id)
        values["summary"].status = "accepted"
        values["document"].status = "accepted"
        assert refresh_event_status(session, event) == "accepted"
        values["document"].status = "failed"
        assert refresh_event_status(session, event) == "partial"
        values["summary"].status = "uncertain"
        values["document"].status = "prepared"
        assert refresh_event_status(session, event) == "uncertain"
