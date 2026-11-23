"""Real and stub Telegram transports."""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from secguard_advisor.config import Settings
from secguard_advisor.notifications.channels.base import (
    StubCall,
    TelegramBot,
    TelegramChat,
    TelegramError,
    TelegramMember,
    TelegramResult,
)


@dataclass
class StubTelegramTransport:
    """Transporte sin red; registra llamadas y permite simular fallos."""

    calls: list[StubCall] = field(default_factory=list)
    fail_on: set[str] = field(default_factory=set)
    uncertain_on: set[str] = field(default_factory=set)
    rate_limit_on: set[str] = field(default_factory=set)
    bot_id: str = "900000001"
    chat_type: str = "private"

    def _result(self, method: str) -> TelegramResult:
        if method in self.rate_limit_on:
            raise TelegramError("rate_limited", "Límite de Telegram.", http_status=429)
        if method in self.uncertain_on:
            raise TelegramError("timeout", "Sin respuesta de Telegram.", uncertain=True)
        if method in self.fail_on:
            raise TelegramError(
                "invalid_request", "Telegram rechazó la solicitud.", http_status=400
            )
        return TelegramResult(True, message_id=str(len(self.calls) + 1000), http_status=200)

    def send_message(self, chat_id: str, text: str) -> TelegramResult:
        self.calls.append(StubCall("send_message", chat_id, text=text))
        return self._result("send_message")

    def send_document(
        self, chat_id: str, filename: str, content: bytes, caption: str
    ) -> TelegramResult:
        self.calls.append(StubCall("send_document", chat_id, filename=filename, content=content))
        return self._result("send_document")

    def get_chat(self, chat_id: str) -> TelegramChat:
        self.calls.append(StubCall("get_chat", chat_id))
        if "get_chat" in self.fail_on:
            raise TelegramError("chat_not_found", "Chat no encontrado.", http_status=400)
        return TelegramChat(chat_id=chat_id, chat_type=self.chat_type, title="Destino ficticio")

    def get_chat_member(self, chat_id: str, user_id: str) -> TelegramMember:
        self.calls.append(StubCall("get_chat_member", chat_id, text=user_id))
        return TelegramMember("member")

    def get_me(self) -> TelegramBot:
        self.calls.append(StubCall("get_me", None))
        return TelegramBot(bot_id=self.bot_id, username="secguard_test_bot")

    def close(self) -> None:
        return None


@dataclass
class RealTelegramTransport:
    """Cliente HTTP real con timeout explícito y sin reintentos internos."""

    settings: Settings
    client: httpx.Client | None = None
    bot_id: str | None = None

    def __post_init__(self) -> None:
        if self.settings.telegram_bot_token is None:
            raise TelegramError("token_missing", "Falta TELEGRAM_BOT_TOKEN.")
        if self.client is None:
            self.client = httpx.Client(timeout=httpx.Timeout(10.0, read=30.0))
            self._owns_client = True
        else:
            self._owns_client = False

    def _url(self, method: str) -> str:
        token = self.settings.telegram_bot_token.get_secret_value()
        return f"{self.settings.telegram_api_base_url.rstrip('/')}/bot{token}/{method}"

    def _call(self, method: str, data: dict, *, files=None) -> dict:
        try:
            response = self.client.post(self._url(method), data=data, files=files)
        except (httpx.TimeoutException, TimeoutError) as exc:
            raise TelegramError(
                "timeout", "Telegram no respondió a tiempo.", uncertain=True
            ) from exc
        except httpx.HTTPError as exc:
            raise TelegramError(
                "provider_error", "Error de red con Telegram.", uncertain=True
            ) from exc
        if response.status_code == 429:
            raise TelegramError("rate_limited", "Límite de Telegram.", http_status=429)
        if response.status_code in {400, 401, 403, 404}:
            code = "forbidden" if response.status_code == 403 else "invalid_request"
            raise TelegramError(
                code, "Telegram rechazó la solicitud.", http_status=response.status_code
            )
        if response.status_code >= 500:
            raise TelegramError(
                "provider_error",
                "Telegram no está disponible.",
                http_status=response.status_code,
                uncertain=True,
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise TelegramError(
                "provider_error", "Respuesta inválida de Telegram.", uncertain=True
            ) from exc
        if not payload.get("ok"):
            description = str(payload.get("description") or "Telegram rechazó la solicitud.")
            raise TelegramError("invalid_request", description, http_status=response.status_code)
        return payload.get("result") or {}

    def send_message(self, chat_id: str, text: str) -> TelegramResult:
        result = self._call("sendMessage", {"chat_id": chat_id, "text": text})
        return TelegramResult(True, message_id=str(result.get("message_id") or ""), http_status=200)

    def send_document(
        self, chat_id: str, filename: str, content: bytes, caption: str
    ) -> TelegramResult:
        result = self._call(
            "sendDocument",
            {"chat_id": chat_id, "caption": caption},
            files={"document": (filename, content, "application/pdf")},
        )
        return TelegramResult(True, message_id=str(result.get("message_id") or ""), http_status=200)

    def get_chat(self, chat_id: str) -> TelegramChat:
        result = self._call("getChat", {"chat_id": chat_id})
        return TelegramChat(
            chat_id=str(result.get("id") or chat_id),
            chat_type=str(result.get("type") or "private"),
            title=result.get("title"),
            username=result.get("username"),
        )

    def get_chat_member(self, chat_id: str, user_id: str) -> TelegramMember:
        result = self._call("getChatMember", {"chat_id": chat_id, "user_id": user_id})
        return TelegramMember(str(result.get("status") or "unknown"))

    def get_me(self) -> TelegramBot:
        result = self._call("getMe", {})
        self.bot_id = str(result.get("id") or "")
        return TelegramBot(bot_id=self.bot_id, username=result.get("username"))

    def close(self) -> None:
        if getattr(self, "_owns_client", False) and self.client is not None:
            self.client.close()


def build_transport(settings: Settings, override=None):
    """Build the configured transport; tests inject a stub explicitly."""
    if override is not None:
        return override
    if settings.telegram_transport == "stub":
        return StubTelegramTransport()
    return RealTelegramTransport(settings)
