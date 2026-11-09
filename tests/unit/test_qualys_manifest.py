"""Pruebas de carga y comparación del manifiesto de referencia."""

from pathlib import Path

import pytest

from secguard_advisor.config import Settings
from secguard_advisor.vulnerabilities.validation import ManifestError, load_manifest, validate_csv

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


def settings() -> Settings:
    return Settings(_env_file=None, storage_dir=Path("."))


def test_loads_manifest_and_matches_synthetic_file() -> None:
    manifest = load_manifest(FIXTURES / "qualys_synthetic_manifest.json")
    result = validate_csv(
        (FIXTURES / "qualys_synthetic_valid.csv").read_bytes(),
        settings=settings(),
        manifest_path=FIXTURES / "qualys_synthetic_manifest.json",
    )
    assert manifest.columns == 41
    assert manifest.output_rows == 5
    assert result.manifest.status == "matched"
    assert result.status == "staged"


def test_valid_manifest_with_different_expected_values_rejects(tmp_path: Path) -> None:
    manifest = load_manifest(FIXTURES / "qualys_synthetic_manifest.json")
    import json

    payload = json.loads((FIXTURES / "qualys_synthetic_manifest.json").read_text(encoding="utf-8"))
    payload["output_detail_rows"] = manifest.output_rows + 1
    path = tmp_path / "mismatch.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_csv(
        (FIXTURES / "qualys_synthetic_valid.csv").read_bytes(),
        settings=settings(),
        manifest_path=path,
    )
    assert result.status == "rejected"
    assert result.manifest.status == "mismatch"
    assert result.error_code == "manifest_mismatch"
    assert result.rows == ()


def test_malformed_manifest_rejects(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ManifestError) as error:
        load_manifest(path)
    assert error.value.code == "manifest_invalid"

    result = validate_csv(
        (FIXTURES / "qualys_synthetic_valid.csv").read_bytes(),
        settings=settings(),
        manifest_path=path,
    )
    assert result.status == "rejected"
    assert result.manifest.status == "invalid"
    assert result.error_code == "manifest_invalid"


def test_absent_manifest_does_not_block_valid_file() -> None:
    result = validate_csv(
        (FIXTURES / "qualys_synthetic_valid.csv").read_bytes(),
        settings=settings(),
    )
    assert result.manifest.status == "absent"
    assert result.status == "staged"
