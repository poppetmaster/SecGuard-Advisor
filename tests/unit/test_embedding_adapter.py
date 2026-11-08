"""Pruebas del adaptador de embeddings con transporte falso."""

import json

import httpx
import pytest

from secguard_advisor.documents.embedding import (
    EmbeddingError,
    EmbeddingTooLong,
    OllamaEmbeddingClient,
)


def _client(handler) -> OllamaEmbeddingClient:
    return OllamaEmbeddingClient(
        base_url="http://ollama.test",
        model="embeddinggemma",
        dimension=4,
        context_tokens=2048,
        transport=httpx.MockTransport(handler),
    )


def test_document_prompt_and_token_count() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "embeddings": [[0.1, 0.2, 0.3, 0.4]],
                "prompt_eval_count": 7,
            },
        )

    client = _client(handler)
    result = client.embed_one("contenido", kind="document", title="Documento")

    assert captured["model"] == "embeddinggemma"
    assert captured["truncate"] is False
    assert captured["input"].startswith("title: Documento | text: ")
    assert result.token_count == 7
    assert result.dimension == 4
    client.close()


def test_query_prompt_uses_task_prefix() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={"embeddings": [[0.0, 0.0, 0.0, 1.0]], "prompt_eval_count": 3},
        )

    client = _client(handler)
    client.embed_one("pregunta", kind="query")

    assert captured["input"].startswith("task: search result | query: ")
    client.close()


def test_too_long_input_raises() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "input length exceeds context"})

    client = _client(handler)

    with pytest.raises(EmbeddingTooLong):
        client.embed_one("x" * 10)
    client.close()


def test_wrong_dimension_is_rejected() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"embeddings": [[0.1, 0.2]], "prompt_eval_count": 2},
        )

    client = _client(handler)

    with pytest.raises(EmbeddingError):
        client.embed_one("texto")
    client.close()


def test_missing_token_count_is_rejected() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2, 0.3, 0.4]]})

    client = _client(handler)

    with pytest.raises(EmbeddingError):
        client.embed_one("texto")
    client.close()


def test_embed_documents_uses_one_request_per_item() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={"embeddings": [[0.1, 0.2, 0.3, 0.4]], "prompt_eval_count": 2},
        )

    client = _client(handler)
    results = client.embed_documents(["a", "b"])

    assert calls == 2
    assert len(results) == 2
    client.close()
