"""Activar un proveedor externo no habilita ni amplía LangSmith (Entrega 2)."""

from secguard_advisor.config import Settings
from secguard_advisor.evidence.tracing import NullTracer, _scrub, build_tracer


def test_external_provider_keeps_langsmith_disabled() -> None:
    settings = Settings(
        _env_file=None,
        generation_provider="deepseek",
        deepseek_api_key="secret",
        langsmith_tracing=False,
    )

    tracer = build_tracer(settings)

    assert isinstance(tracer, NullTracer)
    assert settings.langsmith_tracing is False


def test_trace_metadata_uses_effective_provider_and_redacts() -> None:
    payload = {
        "generator_model": "deepseek-flash",
        "generator_provider": "deepseek",
        "deepseek_api_key": "sk-secret",
        "question": "contenido privado",
    }

    cleaned = _scrub(payload)

    assert cleaned["generator_model"] == "deepseek-flash"
    assert cleaned["deepseek_api_key"] == "***"
    assert cleaned["question"] == "contenido privado"
