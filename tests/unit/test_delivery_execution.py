"""Execution permission, uncertain results and concurrent claims."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import select
from tests.fixtures.notifications import (
    create_ready_report,
    make_confirmation,
    make_eligible_contact,
    make_prepared_event,
)

from secguard_advisor.db.models import NotificationAttempt, NotificationEvent
from secguard_advisor.notifications.channels.telegram import StubTelegramTransport
from secguard_advisor.notifications.delivery import components
from secguard_advisor.notifications.errors import NotificationError
from secguard_advisor.notifications.executor import execute_event, retry_event
from secguard_advisor.notifications.manual import retry_manual, send_manual


def _calls(transport: StubTelegramTransport, method: str) -> int:
    return sum(1 for call in transport.calls if call.method == method)


def test_repeated_send_after_timeout_does_not_resend(report_context) -> None:
    report = create_ready_report(report_context)
    contact, _ = make_eligible_contact(report_context)
    confirmation = make_confirmation(report_context, report, [contact.id])
    transport = StubTelegramTransport()
    transport.uncertain_on.add("send_message")

    send_manual(
        report_context.session_factory,
        report_context.settings,
        transport,
        case_id=report_context.case_id,
        confirmation_id=confirmation.id,
    )
    first_calls = _calls(transport, "send_message")
    assert first_calls == 1

    send_manual(
        report_context.session_factory,
        report_context.settings,
        transport,
        case_id=report_context.case_id,
        confirmation_id=confirmation.id,
    )

    assert _calls(transport, "send_message") == first_calls
    assert _calls(transport, "send_document") == 0
    with report_context.session_factory() as session:
        event = session.scalar(select(NotificationEvent))
        assert event.status == "uncertain"
        values = components(session, event.id)
        assert values["summary"].status == "uncertain"
        assert values["document"].status == "prepared"


def test_accepted_summary_with_uncertain_pdf_is_not_resent_by_retry(report_context) -> None:
    report = create_ready_report(report_context)
    contact, _ = make_eligible_contact(report_context)
    confirmation = make_confirmation(report_context, report, [contact.id])
    transport = StubTelegramTransport()
    transport.uncertain_on.add("send_document")

    send_manual(
        report_context.session_factory,
        report_context.settings,
        transport,
        case_id=report_context.case_id,
        confirmation_id=confirmation.id,
    )
    assert _calls(transport, "send_message") == 1
    assert _calls(transport, "send_document") == 1

    with pytest.raises(NotificationError) as error:
        retry_manual(
            report_context.session_factory,
            report_context.settings,
            transport,
            case_id=report_context.case_id,
            event_id=session_event_id(report_context),
        )
    assert error.value.code == "uncertain_requires_review"
    assert _calls(transport, "send_document") == 1


def test_retry_resends_only_the_failed_document(report_context) -> None:
    report = create_ready_report(report_context)
    contact, _ = make_eligible_contact(report_context)
    confirmation = make_confirmation(report_context, report, [contact.id])
    transport = StubTelegramTransport()
    transport.fail_on.add("send_document")

    send_manual(
        report_context.session_factory,
        report_context.settings,
        transport,
        case_id=report_context.case_id,
        confirmation_id=confirmation.id,
    )
    assert _calls(transport, "send_message") == 1
    assert _calls(transport, "send_document") == 1

    transport.fail_on.discard("send_document")
    status = retry_manual(
        report_context.session_factory,
        report_context.settings,
        transport,
        case_id=report_context.case_id,
        event_id=session_event_id(report_context),
    )

    assert status == "accepted"
    assert _calls(transport, "send_message") == 1
    assert _calls(transport, "send_document") == 2


def test_claim_component_is_atomic_across_sessions(report_context) -> None:
    from secguard_advisor.notifications.delivery import claim_component

    report = create_ready_report(report_context)
    contact, _ = make_eligible_contact(report_context)
    confirmation = make_confirmation(report_context, report, [contact.id])
    event_id, _manifest = make_prepared_event(report_context, contact, confirmation)

    with report_context.session_factory() as first:
        event = first.get(NotificationEvent, event_id)
        assert claim_component(first, event=event, kind="summary") is not None
        first.commit()
    with report_context.session_factory() as second:
        event = second.get(NotificationEvent, event_id)
        assert claim_component(second, event=event, kind="summary") is None
        second.commit()

    with report_context.session_factory() as session:
        assert components(session, event_id)["summary"].attempt_count == 1


def test_two_concurrent_executions_claim_each_component_once(report_context) -> None:
    report = create_ready_report(report_context)
    contact, _ = make_eligible_contact(report_context)
    confirmation = make_confirmation(report_context, report, [contact.id])
    event_id, _manifest = make_prepared_event(report_context, contact, confirmation)
    transport = StubTelegramTransport()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                execute_event,
                report_context.session_factory,
                report_context.settings,
                transport,
                event_id,
            )
            for _ in range(2)
        ]
        [future.result() for future in futures]

    assert _calls(transport, "send_message") == 1
    assert _calls(transport, "send_document") == 1
    with report_context.session_factory() as session:
        values = components(session, event_id)
        assert values["summary"].attempt_count == 1
        assert values["document"].attempt_count == 1
        attempts = list(
            session.scalars(
                select(NotificationAttempt).where(NotificationAttempt.event_id == event_id)
            )
        )
        assert len(attempts) == 2


def test_retry_refuses_while_another_request_is_in_flight(report_context) -> None:
    report = create_ready_report(report_context)
    contact, _ = make_eligible_contact(report_context)
    confirmation = make_confirmation(report_context, report, [contact.id])
    event_id, _manifest = make_prepared_event(report_context, contact, confirmation)
    with report_context.session_factory() as session:
        components(session, event_id)["summary"].status = "requested"
        session.commit()
    transport = StubTelegramTransport()

    with pytest.raises(NotificationError) as error:
        retry_event(report_context.session_factory, report_context.settings, transport, event_id)
    assert error.value.code == "uncertain_requires_review"
    assert transport.calls == []


def session_event_id(report_context) -> str:
    with report_context.session_factory() as session:
        return session.scalar(select(NotificationEvent.id))
