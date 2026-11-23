"""Telegram transport contract and safe result types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class TelegramError(RuntimeError):
    """Error de transporte con código seguro y carácter incierto opcional."""

    def __init__(
        self, code: str, message: str, *, http_status: int | None = None, uncertain: bool = False
    ) -> None:
        self.code = code
        self.message = message
        self.http_status = http_status
        self.uncertain = uncertain
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class TelegramResult:
    ok: bool
    message_id: str | None = None
    http_status: int | None = None
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class TelegramChat:
    chat_id: str
    chat_type: str
    title: str | None = None
    username: str | None = None


@dataclass(frozen=True, slots=True)
class TelegramMember:
    status: str


@dataclass(frozen=True, slots=True)
class TelegramBot:
    bot_id: str
    username: str | None = None


@dataclass(frozen=True, slots=True)
class StubCall:
    method: str
    chat_id: str | None
    text: str | None = None
    filename: str | None = None
    content: bytes | None = None


class TelegramTransport(Protocol):
    def send_message(self, chat_id: str, text: str) -> TelegramResult: ...
    def send_document(
        self, chat_id: str, filename: str, content: bytes, caption: str
    ) -> TelegramResult: ...
    def get_chat(self, chat_id: str) -> TelegramChat: ...
    def get_chat_member(self, chat_id: str, user_id: str) -> TelegramMember: ...
    def get_me(self) -> TelegramBot: ...
    def close(self) -> None: ...
