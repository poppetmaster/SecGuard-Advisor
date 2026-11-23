"""Outbound content and event views do not expose private data."""

from __future__ import annotations

from tests.fixtures.notifications import create_ready_report, make_eligible_contact

from secguard_advisor.db.models import ReportVersion
from secguard_advisor.notifications.delivery import ensure_event, event_view
from secguard_advisor.notifications.manifest import build_manifest


def test_manifest_and_event_view_are_private(report_context) -> None:
    result = create_ready_report(report_context)
    contact, _ = make_eligible_contact(report_context, chat_id="987654321")
    with report_context.session_factory() as session:
        version = session.get(ReportVersion, result.version_id)
        manifest = build_manifest(session, version, [contact.id])
        event, _ = ensure_event(
            session, version=version, contact=contact, manifest=manifest, mode="manual"
        )
        session.commit()
        view = event_view(session, event)
    text = manifest["outbound_text"]
    assert "host-01.example" not in text
    assert "10.0.0.1" not in text
    assert "Caso ficticio 006" not in text
    assert "987654321" not in str(view)
    assert view["masked_chat"].startswith("••••")
    assert "token" not in str(view).lower()
