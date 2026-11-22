"""Contrato común de generadores y errores de selección."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from secguard_advisor.conversation.llm import AnswerPayload, ToolDecision


class ProviderAuthError(RuntimeError):
    """La credencial fue rechazada por el proveedor."""

    code = "provider_auth_error"


class ProviderRateLimited(RuntimeError):
    """El proveedor aplicó un límite de tasa."""

    code = "provider_rate_limited"


class ProviderError(RuntimeError):
    """Error del proveedor no clasificado."""

    code = "provider_error"


class ProviderNotImplemented(RuntimeError):
    """El proveedor está configurado pero todavía no tiene adaptador."""

    code = "provider_not_implemented"

    def __init__(self, provider: str, model: str) -> None:
        self.provider = provider
        self.model = model
        super().__init__(
            f"El proveedor {provider} ({model}) todavía no está implementado. "
            "Usá Ollama mientras dure la Entrega 1."
        )


@runtime_checkable
class GeneratorProtocol(Protocol):
    """Interfaz que consumen el grafo y el turno, sin conocer el proveedor."""

    provider: str
    model: str
    identity: str | None
    last_usage: dict | None

    def decide(
        self, *, system: str, user: str, timeout_seconds: float | None = None
    ) -> ToolDecision: ...

    def generate(
        self, *, system: str, user: str, timeout_seconds: float | None = None
    ) -> AnswerPayload: ...

    def close(self) -> None: ...
