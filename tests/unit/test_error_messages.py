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


QDRANT_ERRORS = {
    "qdrant_unavailable": 503,
    "case_index_unavailable": 503,
    "public_index_unavailable": 503,
    "instance_namespace_mismatch": 503,
    "reconstruction_in_progress": 409,
    "ingestion_in_progress": 409,
}


def test_qdrant_codes_keep_their_own_code_and_status() -> None:
    for code, status in QDRANT_ERRORS.items():
        spec = ERRORS[code]
        assert spec.code == code
        assert spec.status == status
        assert spec.message
        assert AppError(code).code == code
        assert AppError(code).status == status


def test_qdrant_codes_are_not_demoted_to_internal_error() -> None:
    for code in QDRANT_ERRORS:
        assert AppError(code).code != "internal_error"
        assert message_for(code) != message_for("internal_error")
