"""Pruebas del lector y la validación del CSV Qualys."""

from pathlib import Path

import pytest

from secguard_advisor.config import Settings
from secguard_advisor.vulnerabilities.adapter import EXPECTED_COLUMNS, CsvReadError, read_csv
from secguard_advisor.vulnerabilities.validation import validate_csv

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


def settings(**overrides) -> Settings:
    return Settings(_env_file=None, storage_dir=Path("."), **overrides)


def test_reads_bom_header_and_multiline_fields() -> None:
    content = (FIXTURES / "qualys_synthetic_valid.csv").read_bytes()
    result = read_csv(content, max_bytes=10 * 1024 * 1024, max_rows=100)
    assert result.header == EXPECTED_COLUMNS
    assert len(result.rows) == 5
    assert "\n" in result.rows[0]["Exploitability"]


def test_header_mismatch_and_empty_file_are_structural_errors() -> None:
    with pytest.raises(CsvReadError) as header:
        read_csv(
            (FIXTURES / "qualys_synthetic_invalid_header.csv").read_bytes(),
            max_bytes=10_000,
            max_rows=10,
        )
    assert header.value.code == "header_mismatch"
    with pytest.raises(CsvReadError) as empty:
        read_csv(
            (FIXTURES / "qualys_synthetic_empty.csv").read_bytes(), max_bytes=10_000, max_rows=10
        )
    assert empty.value.code == "empty_file"


def test_read_limits() -> None:
    content = (FIXTURES / "qualys_synthetic_valid.csv").read_bytes()
    with pytest.raises(CsvReadError) as too_big:
        read_csv(content, max_bytes=10, max_rows=100)
    assert too_big.value.code == "file_too_large"
    with pytest.raises(CsvReadError) as too_many:
        read_csv(content, max_bytes=10_000, max_rows=1)
    assert too_many.value.code == "too_many_rows"


def test_valid_fixture_is_staged_with_counts_and_manifest() -> None:
    content = (FIXTURES / "qualys_synthetic_valid.csv").read_bytes()
    result = validate_csv(
        content,
        settings=settings(),
        manifest_path=FIXTURES / "qualys_synthetic_manifest.json",
    )
    assert result.status == "staged"
    assert result.manifest.status == "matched"
    assert result.row_count == 5
    assert result.valid_rows == 5
    assert result.invalid_rows == 0
    assert result.status_counts == {
        "Active": 1,
        "New": 1,
        "Re-Opened": 1,
        "Fixed": 1,
        "UnknownState": 1,
    }
    assert result.exploitability_counts == {"positive": 3, "indeterminate": 2}
    assert result.malware_counts == {"positive": 2, "indeterminate": 2, "negative_no_info": 1}
    assert result.priority_counts == {"both_positive": 2}
    assert result.possible_repeat_groups == 1
    assert result.possible_repeat_rows == 1
    assert result.rows[0].cves == ("CVE-2024-0001", "CVE-2024-12345")
    assert result.rows[2].cves == ("CVE-2026-1234567",)


def test_invalid_rows_reject_the_whole_file() -> None:
    result = validate_csv(
        (FIXTURES / "qualys_synthetic_invalid_rows.csv").read_bytes(),
        settings=settings(),
    )
    assert result.status == "rejected"
    assert result.error_code == "invalid_severity"
    assert result.invalid_rows == 3
    assert result.rows == ()
    assert {issue.code for issue in result.issues} >= {
        "invalid_severity",
        "invalid_date",
        "invalid_qid",
        "invalid_cve",
    }


def test_empty_file_is_rejected_with_zero_bytes() -> None:
    result = validate_csv(
        (FIXTURES / "qualys_synthetic_empty.csv").read_bytes(),
        settings=settings(),
    )
    assert result.status == "rejected"
    assert result.error_code == "empty_file"
    assert result.row_count == 0


def test_unknown_status_and_indeterminate_indicators_are_not_blocking() -> None:
    result = validate_csv(
        (FIXTURES / "qualys_synthetic_mixed.csv").read_bytes(),
        settings=settings(),
    )
    assert result.status == "staged"
    assert result.manual_review_rows >= 1
    assert any(issue.code == "unknown_status" for issue in result.issues)
    assert any(issue.code == "indicator_indeterminate" for issue in result.issues)


def test_field_limit_is_a_blocking_error(tmp_path: Path) -> None:
    from tests.fixtures.qualys import make_row, write_csv

    row = make_row(Title="x" * 30)
    path = tmp_path / "long.csv"
    content = write_csv(path, [row])
    result = validate_csv(content, settings=settings(qualys_max_field_chars=10))
    assert result.status == "rejected"
    assert result.error_code == "field_too_long"
