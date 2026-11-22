"""Redacción centralizada de secretos y rutas (Entrega 2)."""

from secguard_advisor.conversation.providers.redaction import redact_text, redact_value
from secguard_advisor.evidence.tracing import _scrub


def test_redact_text_removes_keys_and_paths() -> None:
    text = "fallo sk-ant-api03-secret12345 en /Users/privado/archivo"

    cleaned = redact_text(text)

    assert "sk-ant-api03-secret12345" not in cleaned
    assert "/Users/privado/archivo" not in cleaned
    assert "***" in cleaned
    assert "[ruta]" in cleaned


def test_redact_value_removes_secret_named_fields() -> None:
    payload = {
        "authorization": "Bearer secret",
        "deepseek_api_key": "sk-secret",
        "nested": {"anthropic_api_key": "sk-ant-secret", "safe": "valor"},
    }

    cleaned = redact_value(payload)

    assert cleaned["authorization"] == "***"
    assert cleaned["deepseek_api_key"] == "***"
    assert cleaned["nested"]["anthropic_api_key"] == "***"
    assert cleaned["nested"]["safe"] == "valor"


def test_trace_scrub_removes_secret_fields_and_patterns() -> None:
    cleaned = _scrub(
        {
            "anthropic_api_key": "sk-ant-secret",
            "message": "clave sk-abcdefgh12345678 y /private/dato",
        }
    )

    assert cleaned["anthropic_api_key"] == "***"
    assert "sk-abcdefgh12345678" not in cleaned["message"]
    assert "[ruta]" in cleaned["message"]
