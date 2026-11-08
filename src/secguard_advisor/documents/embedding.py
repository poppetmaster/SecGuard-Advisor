"""Adaptador de embeddings sobre la API de Ollama."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import httpx


class EmbeddingError(Exception):
    """La generación de embeddings falló."""


class EmbeddingTooLong(EmbeddingError):
    """La entrada excede el contexto del modelo."""


@dataclass(frozen=True, slots=True)
class EmbeddingResult:
    vector: list[float]
    token_count: int
    model: str
    dimension: int
    prompt: str


class OllamaEmbeddingClient:
    """Cliente que mide una entrada por petición y prohíbe el truncado."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        dimension: int,
        context_tokens: int = 2048,
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.model = model
        self.dimension = dimension
        self.context_tokens = context_tokens
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def _prompt(
        self,
        text: str,
        *,
        kind: Literal["query", "document"],
        title: str | None,
    ) -> str:
        if kind == "query":
            return f"task: search result | query: {text}"
        return f"title: {title or 'none'} | text: {text}"

    def embed_one(
        self,
        text: str,
        *,
        kind: Literal["query", "document"] = "document",
        title: str | None = None,
    ) -> EmbeddingResult:
        """Genera el embedding de una sola entrada y mide sus tokens."""
        prompt = self._prompt(text, kind=kind, title=title)
        response = self._client.post(
            "/api/embed",
            json={"model": self.model, "input": prompt, "truncate": False},
        )

        if response.status_code == 400:
            message = response.text.lower()
            if "too long" in message or "context" in message or "truncate" in message:
                raise EmbeddingTooLong("La entrada excede el contexto del modelo de embeddings.")
            raise EmbeddingError("Ollama rechazó la entrada de embeddings.")
        try:
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise EmbeddingError("No se pudo generar el embedding.") from exc

        payload = response.json()
        embeddings = payload.get("embeddings") or []
        if len(embeddings) != 1:
            raise EmbeddingError("Ollama no devolvió exactamente un embedding.")
        vector = embeddings[0]
        if len(vector) != self.dimension:
            raise EmbeddingError(
                f"Dimensión inesperada: {len(vector)} en lugar de {self.dimension}."
            )

        token_count = payload.get("prompt_eval_count")
        if not isinstance(token_count, int):
            raise EmbeddingError("Ollama no informó el conteo de tokens.")
        if token_count > self.context_tokens:
            raise EmbeddingTooLong("La entrada excede el contexto del modelo de embeddings.")

        return EmbeddingResult(
            vector=vector,
            token_count=token_count,
            model=self.model,
            dimension=self.dimension,
            prompt=prompt,
        )

    def embed_documents(
        self,
        texts: Sequence[str],
        *,
        titles: Sequence[str | None] | None = None,
    ) -> list[EmbeddingResult]:
        """Mide cada documento en una petición separada."""
        resolved_titles = list(titles) if titles is not None else [None] * len(texts)
        return [
            self.embed_one(text, kind="document", title=title)
            for text, title in zip(texts, resolved_titles, strict=True)
        ]
