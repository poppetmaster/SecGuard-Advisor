"""Reports migration is additive and reversible."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from secguard_advisor.config import get_settings


def test_reports_migration_upgrade_and_downgrade(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SECGUARD_STORAGE_DIR", str(tmp_path / "storage"))
    get_settings.cache_clear()
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{tmp_path / 'storage' / 'secguard.sqlite3'}")
    tables = set(inspect(engine).get_table_names())
    assert {"reports", "report_versions", "report_artifacts"} <= tables
    columns = {column["name"] for column in inspect(engine).get_columns("report_versions")}
    assert "generation_key" in columns
    engine.dispose()

    command.downgrade(config, "-1")
    engine = create_engine(f"sqlite:///{tmp_path / 'storage' / 'secguard.sqlite3'}")
    tables = set(inspect(engine).get_table_names())
    assert "reports" not in tables
    engine.dispose()
    get_settings.cache_clear()
