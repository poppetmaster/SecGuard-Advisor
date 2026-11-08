"""Dobles de prueba deterministas para embeddings y generación."""

import hashlib
from collections.abc import Sequence


class FakeEmbeddings:
    """Embeddings deterministas basados en SHA-256."""

    def __init__(self, dimension: int = 8) -> None:
        self.dimension = dimension

    def _vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        repeated = (digest * ((self.dimension // len(digest)) + 1))[: self.dimension]
        return [byte / 255 for byte in repeated]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]


class FakeLLM:
    """Generador falso con una respuesta controlada."""

    def __init__(self, response: str = '{"answer":"ok"}') -> None:
        self.response = response

    def invoke(self, _messages: object) -> str:
        return self.response


class FakeEmbedder:
    """Embeddings deterministas con conteo de tokens controlado."""

    model = "fake-embedding"
    dimension = 4

    def __init__(
        self,
        *,
        token_count: int = 10,
        fail: bool = False,
        too_long_over: int | None = None,
    ) -> None:
        self.token_count = token_count
        self.fail = fail
        self.too_long_over = too_long_over

    def embed_one(self, text: str, *, kind: str = "document", title: str | None = None):
        from secguard_advisor.documents.embedding import (
            EmbeddingError,
            EmbeddingResult,
            EmbeddingTooLong,
        )

        if self.fail:
            raise EmbeddingError("fallo simulado de embeddings")
        if self.too_long_over is not None and len(text) > self.too_long_over:
            raise EmbeddingTooLong("entrada demasiado larga")
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        vector = [byte / 255 for byte in digest[: self.dimension]]
        return EmbeddingResult(
            vector=vector,
            token_count=min(self.token_count, 2048),
            model=self.model,
            dimension=self.dimension,
            prompt=text,
        )

    def close(self) -> None:
        return None


class FakeIndex:
    """Índice en memoria para pruebas rápidas."""

    def __init__(self, *, fail: bool = False) -> None:
        self.chunks: dict[str, object] = {}
        self.deleted_versions: set[str] = set()
        self.fail = fail

    def upsert(self, scope, model: str, dimension: int, chunks) -> None:
        if self.fail:
            raise RuntimeError("fallo simulado del índice")
        for chunk in chunks:
            self.chunks[chunk.chunk_id] = chunk

    def delete_version(self, scope, model: str, dimension: int, version_id: str) -> None:
        self.deleted_versions.add(version_id)
        for chunk_id, chunk in list(self.chunks.items()):
            if chunk.version_id == version_id:
                del self.chunks[chunk_id]

    def count(self) -> int:
        return len(self.chunks)


class ScriptedGenerator:
    """Generador guionizado: devuelve respuestas en orden o falla."""

    model = "fake-generator"
    digest = "digest-fake"

    def __init__(self, payloads=None, *, error: Exception | None = None) -> None:
        from secguard_advisor.conversation.llm import AnswerPayload

        self.payloads = list(payloads or [AnswerPayload(answer="respuesta", claims=[])])
        self.error = error
        self.calls = 0
        self.prompts: list[str] = []

    def generate(self, *, system: str, user: str):
        self.calls += 1
        self.prompts.append(user)
        if self.error is not None:
            raise self.error
        if not self.payloads:
            from secguard_advisor.conversation.llm import AnswerPayload

            return AnswerPayload(answer="respuesta", claims=[])
        return self.payloads.pop(0)
