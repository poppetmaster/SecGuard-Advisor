"""Telegram transport stub and real token gate."""

from __future__ import annotations

import pytest

from secguard_advisor.config import Settings
from secguard_advisor.notifications.channels.base import TelegramError
from secguard_advisor.notifications.channels.telegram import (
    RealTelegramTransport,
    StubTelegramTransport,
    build_transport,
)


def test_stub_records_without_network() -> None:
    transport = StubTelegramTransport()
    result = transport.send_message("123456789", "hola")
    assert result.ok and result.message_id
    assert transport.calls[0].method == "send_message"
    assert transport.get_me().bot_id == "900000001"


def test_stub_can_simulate_timeout_and_rate_limit() -> None:
    transport = StubTelegramTransport(uncertain_on={"send_message"})
    with pytest.raises(TelegramError) as error:
        transport.send_message("123456789", "hola")
    assert error.value.uncertain is True
    transport = StubTelegramTransport(rate_limit_on={"send_document"})
    with pytest.raises(TelegramError) as error:
        transport.send_document("123456789", "a.pdf", b"%PDF", "caption")
    assert error.value.code == "rate_limited"


def test_real_transport_requires_token() -> None:
    settings = Settings(_env_file=None)
    with pytest.raises(TelegramError) as error:
        RealTelegramTransport(settings)
    assert error.value.code == "token_missing"


def test_build_transport_defaults_to_stub() -> None:
    settings = Settings(_env_file=None)
    assert isinstance(build_transport(settings), StubTelegramTransport)
