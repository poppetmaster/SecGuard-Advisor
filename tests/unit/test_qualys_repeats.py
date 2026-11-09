"""Pruebas de posibles repeticiones sin deduplicación silenciosa."""

from pathlib import Path

from secguard_advisor.config import Settings
from secguard_advisor.vulnerabilities.validation import validate_csv

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


def test_repeated_combination_is_reported_and_preserved() -> None:
    result = validate_csv(
        (FIXTURES / "qualys_synthetic_valid.csv").read_bytes(),
        settings=Settings(_env_file=None, storage_dir=Path(".")),
    )
    assert result.status == "staged"
    assert result.row_count == 5
    assert len(result.rows) == 5
    assert result.possible_repeat_groups == 1
    assert result.possible_repeat_rows == 1
    repeated = [row for row in result.rows if row.qid == "900001"]
    assert len(repeated) == 2
    assert all(row.row_number in {1, 2} for row in repeated)
