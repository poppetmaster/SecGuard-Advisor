"""Stable report error codes."""

from secguard_advisor.reports.errors import REPORT_ERROR_CODES, ReportError, report_error


def test_error_codes_are_safe_and_stable() -> None:
    assert (
        "manifest_mismatch"
        in __import__(
            "secguard_advisor.notifications.errors", fromlist=["NOTIFICATION_ERROR_CODES"]
        ).NOTIFICATION_ERROR_CODES
    )
    for code, message in REPORT_ERROR_CODES.items():
        assert code and message
        assert "token" not in message.lower()
        assert "chat_id" not in message.lower()
    error = report_error("pdf_not_ready")
    assert isinstance(error, ReportError)
    assert error.status == 422
