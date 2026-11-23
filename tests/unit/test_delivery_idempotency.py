"""Event identity and component independence."""

from __future__ import annotations

from tests.fixtures.notifications import create_ready_report, make_eligible_contact

from secguard_advisor.db.models import ReportVersion
from secguard_advisor.notifications.delivery import components, ensure_event
from secguard_advisor.notifications.manifest import build_manifest


def test_idempotency_key_does_not_include_mode(report_context) -> None:
    result = create_ready_report(report_context)
    contact, _ = make_eligible_contact(report_context)
    with report_context.session_factory() as session:
        version = session.get(ReportVersion, result.version_id)
        manifest = build_manifest(session, version, [contact.id])
        first, created = ensure_event(
            session, version=version, contact=contact, manifest=manifest, mode="manual"
        )
        second, created_again = ensure_event(
            session, version=version, contact=contact, manifest=manifest, mode="automatic"
        )
        session.commit()
        assert created is True and created_again is False
        assert first.id == second.id
        assert len(components(session, first.id)) == 2


def test_accepted_component_cannot_return_to_requested(report_context) -> None:
    result = create_ready_report(report_context)
    contact, _ = make_eligible_contact(report_context)
    with report_context.session_factory() as session:
        version = session.get(ReportVersion, result.version_id)
        manifest = build_manifest(session, version, [contact.id])
        event, _ = ensure_event(
            session, version=version, contact=contact, manifest=manifest, mode="manual"
        )
        summary = components(session, event.id)["summary"]
        summary.status = "accepted"
        session.flush()
        from secguard_advisor.notifications.delivery import set_component

        try:
            set_component(session, event=event, kind="summary", status="requested")
        except Exception as exc:
            assert getattr(exc, "code", None) == "accepted_component"
        else:  # pragma: no cover
            raise AssertionError("Un componente aceptado no debe reenviarse")
