"""Pruebas del formato de logging y de la redacción de secretos."""

import logging

from secguard_advisor.logging import ContextFilter, configure_logging, log_event


def test_event_format_includes_context(capsys) -> None:
    configure_logging(logging.INFO)
    log_event(logging.getLogger("secguard.test"), "prueba", run_id="r1", case_id="c1")

    captured = capsys.readouterr().err

    assert "run_id=r1" in captured
    assert "case_id=c1" in captured
    assert "event=prueba" in captured


def test_secret_attribute_is_redacted() -> None:
    record = logging.LogRecord(
        name="secguard.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="mensaje",
        args=None,
        exc_info=None,
    )
    record.api_key = "super-secret"

    ContextFilter().filter(record)

    assert record.api_key == "***"
