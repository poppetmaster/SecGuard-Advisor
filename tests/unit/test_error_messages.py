"""Pruebas de la taxonomía de errores."""

import json

from secguard_advisor.web.errors import ERRORS, AppError, error_response, message_for


def test_every_code_has_a_message_and_status() -> None:
    for code, spec in ERRORS.items():
        assert spec.code == code
        assert spec.status >= 400
        assert spec.message
        assert message_for(code) == spec.message


def test_app_error_exposes_code_and_status() -> None:
    error = AppError("not_found")

    assert error.code == "not_found"
    assert error.status == 404
    assert error.message == ERRORS["not_found"].message


def test_error_response_is_json_and_has_no_traceback() -> None:
    response = error_response("busy")

    payload = json.loads(response.body)

    assert response.status_code == 429
    assert payload["error"]["code"] == "busy"
    assert "Traceback" not in response.body.decode()
