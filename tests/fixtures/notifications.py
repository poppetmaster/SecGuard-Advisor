"""Helpers for Corte B tests with a stub Telegram transport."""

from __future__ import annotations

from pathlib import Path

from secguard_advisor.db.models import ContactChannel
from secguard_advisor.notifications.channels.telegram import StubTelegramTransport
from secguard_advisor.notifications.contacts import (
    authorize_case,
    create_contact,
    set_active,
    set_consent,
)
from secguard_advisor.notifications.verification import confirm_verification, start_verification
from secguard_advisor.reports.service import ReportVersionResult, create_report_version
from tests.fixtures.report_fixtures import ReportContext


def fake_charts(_settings, charts):
    return {key: f"<svg>{key}</svg>" for key in charts}


def fake_pdf(_settings, _html, path: Path):
    data = b"%PDF-1.4\n% fictional report\n%%EOF\n"
    path.write_bytes(data)
    return data


def create_ready_report(context: ReportContext) -> ReportVersionResult:
    with context.session_factory() as session:
        result = create_report_version(
            session,
            context.settings,
            case_id=context.case_id,
            snapshot_id=context.snapshot_id,
            author="Prueba Corte B",
            synthesize=False,
            chart_renderer=fake_charts,
            pdf_renderer=fake_pdf,
        )
        session.commit()
        return result


def code_from_stub(transport: StubTelegramTransport) -> str:
    for call in reversed(transport.calls):
        if call.method == "send_message" and call.text and "Código" in call.text:
            return call.text.split(": ", 1)[1].split(".", 1)[0]
    raise AssertionError("No se encontró el código en el transporte doble")


def make_eligible_contact(
    context: ReportContext,
    *,
    alias: str = "Operaciones",
    chat_id: str = "123456789",
    transport: StubTelegramTransport | None = None,
) -> tuple[ContactChannel, StubTelegramTransport]:
    transport = transport or StubTelegramTransport()
    with context.session_factory() as session:
        contact = create_contact(session, alias=alias, chat_id=chat_id)
        session.commit()
        contact_id = contact.id
    with context.session_factory() as session:
        start_verification(session, contact_id=contact_id, transport=transport)
        session.commit()
    code = code_from_stub(transport)
    with context.session_factory() as session:
        confirm_verification(session, contact_id=contact_id, code=code, verified_by="Prueba")
        set_consent(session, contact_id, "granted", declared_by="Prueba")
        set_active(session, contact_id, True)
        authorize_case(session, contact_id=contact_id, case_id=context.case_id, authorized=True)
        session.commit()
        contact = session.get(ContactChannel, contact_id)
        session.expunge(contact)
        return contact, transport
