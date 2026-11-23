"""Canonical report manifest."""

from __future__ import annotations

from tests.fixtures.notifications import create_ready_report, make_eligible_contact

from secguard_advisor.db.models import ReportVersion
from secguard_advisor.notifications.manifest import build_manifest


def test_manifest_has_hashes_and_masks_recipients(report_context) -> None:
    result = create_ready_report(report_context)
    contact, _ = make_eligible_contact(report_context)
    with report_context.session_factory() as session:
        version = session.get(ReportVersion, result.version_id)
        manifest = build_manifest(session, version, [contact.id])
    assert manifest["schema_version"] == "report-manifest-v1"
    assert manifest["dataset_sha256"] == result.dataset_sha256
    assert manifest["pdf_sha256"]
    assert manifest["outbound_text_sha256"]
    assert manifest["recipients_sha256"]
    assert manifest["manifest_sha256"]
    recipient = manifest["recipients"][0]
    assert recipient["contact_id"] == contact.id
    assert recipient["masked_chat"].startswith("••••")
    assert "chat_id" not in recipient
    assert "token" not in str(manifest).lower()
    assert "host-01.example" not in manifest["outbound_text"]
    assert "Caso ficticio 006" not in manifest["outbound_text"]


def test_manifest_changes_when_recipient_alias_changes(report_context) -> None:
    result = create_ready_report(report_context)
    contact, _ = make_eligible_contact(report_context)
    with report_context.session_factory() as session:
        version = session.get(ReportVersion, result.version_id)
        first = build_manifest(session, version, [contact.id])
        persisted = session.get(type(contact), contact.id)
        persisted.alias = "Otro alias"
        session.flush()
        second = build_manifest(session, version, [contact.id])
    assert first["manifest_sha256"] != second["manifest_sha256"]
