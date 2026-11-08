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
