"""Pruebas del cliente de generación y del prompt."""

from __future__ import annotations

import httpx
import pytest

from secguard_advisor.conversation.llm import (
    AnswerPayload,
    GenerationConfig,
    InvalidModelOutput,
    ModelTimeout,
    ModelUnavailable,
    OllamaGenerator,
)
from secguard_advisor.conversation.prompts import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_prompt,
)
from secguard_advisor.retrieval.search import RetrievedChunk


def _config() -> GenerationConfig:
    return GenerationConfig(
        base_url="http://ollama.test",
        model="qwen3.5:9b",
        num_ctx=8192,
        temperature=0.1,
        seed=42,
        timeout_seconds=30.0,
    )


class StubStructured:
    def __init__(self, *, result=None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error

    def invoke(self, _messages):
        if self.error is not None:
            raise self.error
        return self.result


class StubChat:
    def __init__(self, structured: StubStructured) -> None:
        self.structured = structured
        self.schema = None
        self.method = None
        self.include_raw = None

    def with_structured_output(self, schema, *, method="json_schema", include_raw=False):
        self.schema = schema
        self.method = method
        self.include_raw = include_raw
        return self.structured


def _generator_with(monkeypatch, structured: StubStructured) -> tuple[OllamaGenerator, dict]:
    captured: dict = {}

    def fake_chat(self):
        captured["kwargs"] = {
            "model": self.config.model,
            "base_url": self.config.base_url,
            "num_ctx": self.config.num_ctx,
            "temperature": self.config.temperature,
            "seed": self.config.seed,
            "num_predict": self.config.num_predict,
            "timeout": self.config.timeout_seconds,
        }
        captured["chat"] = StubChat(structured)
        return captured["chat"]

    monkeypatch.setattr(OllamaGenerator, "_chat", fake_chat)
    return OllamaGenerator(_config()), captured


def test_structured_output_uses_json_schema(monkeypatch) -> None:
    payload = AnswerPayload(answer="hola", claims=[])
    generator, captured = _generator_with(monkeypatch, StubStructured(result=payload))

    result = generator.generate(system="s", user="u")

    assert result.answer == "hola"
    assert captured["chat"].schema is AnswerPayload
    assert captured["chat"].method == "json_schema"
    assert captured["chat"].include_raw is True
    assert captured["kwargs"]["model"] == "qwen3.5:9b"
    assert captured["kwargs"]["num_ctx"] == 8192
    assert captured["kwargs"]["temperature"] == 0.1
    assert captured["kwargs"]["seed"] == 42
    assert captured["kwargs"]["timeout"] == 30.0


def test_dict_output_is_validated(monkeypatch) -> None:
    generator, _captured = _generator_with(
        monkeypatch,
        StubStructured(result={"answer": "dict", "claims": [], "missing_info": []}),
    )

    result = generator.generate(system="s", user="u")

    assert isinstance(result, AnswerPayload)
    assert result.answer == "dict"


def test_connection_error_is_model_unavailable(monkeypatch) -> None:
    generator, _captured = _generator_with(
        monkeypatch, StubStructured(error=ConnectionError("connection refused"))
    )

    with pytest.raises(ModelUnavailable):
        generator.generate(system="s", user="u")


def test_timeout_is_model_timeout(monkeypatch) -> None:
    generator, _captured = _generator_with(
        monkeypatch, StubStructured(error=TimeoutError("timed out"))
    )

    with pytest.raises(ModelTimeout):
        generator.generate(system="s", user="u")


def test_invalid_output_is_classified(monkeypatch) -> None:
    generator, _captured = _generator_with(monkeypatch, StubStructured(error=ValueError("no json")))

    with pytest.raises(InvalidModelOutput):
        generator.generate(system="s", user="u")


def test_missing_digest_is_not_invented(monkeypatch) -> None:
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *_args, **_kwargs: httpx.Response(200, json={"models": []}),
    )
    generator = OllamaGenerator(_config())

    assert generator.resolve_digest() is None


def test_prompt_version_and_rules() -> None:
    assert PROMPT_VERSION == "chat-v2"
    folded = SYSTEM_PROMPT.casefold()
    for rule in (
        "cita literal",
        "missing_info",
        "parafrasear",
        "no inventes cifras",
        "dato no confiable",
        "certificaciones",
        "no inventes identificadores",
        "no es evidencia",
    ):
        assert rule in folded
    lowered = SYSTEM_PROMPT.casefold()
    for secret in ("api_key", "apikey", "password", "sk-", "token="):
        assert secret not in lowered


def test_user_prompt_lists_sources_with_ids() -> None:
    hit = RetrievedChunk(
        chunk_id="a" * 32,
        document_id="b" * 32,
        version_id="c" * 32,
        document_title="CSF 2.0",
        declared_version="NIST CSWP 29",
        origin="public_corpus",
        page=12,
        section="GOVERN",
        locator="p:12#0",
        text="Texto del fragmento",
        score=0.8,
        version_current=True,
    )

    prompt = build_user_prompt("¿Qué es GOVERN?", (hit,))

    assert "¿Qué es GOVERN?" in prompt
    assert "a" * 32 in prompt
    assert "página 12" in prompt
    assert "Texto del fragmento" in prompt


def test_observed_usage_is_recorded(monkeypatch) -> None:
    from langchain_core.messages import AIMessage

    payload = AnswerPayload(answer="hola", claims=[])
    raw = AIMessage(
        content="",
        response_metadata={"prompt_eval_count": 1234, "eval_count": 56},
    )
    generator, _captured = _generator_with(
        monkeypatch,
        StubStructured(result={"raw": raw, "parsed": payload, "parsing_error": None}),
    )

    result = generator.generate(system="s", user="u")

    assert result.answer == "hola"
    assert generator.last_usage == {"prompt_tokens": 1234, "output_tokens": 56}


def test_parsing_error_with_raw_output_is_invalid(monkeypatch) -> None:
    from langchain_core.messages import AIMessage

    generator, _captured = _generator_with(
        monkeypatch,
        StubStructured(
            result={
                "raw": AIMessage(content="no json"),
                "parsed": None,
                "parsing_error": ValueError("no json"),
            }
        ),
    )

    with pytest.raises(InvalidModelOutput):
        generator.generate(system="s", user="u")
