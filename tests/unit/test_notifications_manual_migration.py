"""Manual delivery migration is additive and reversible."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from secguard_advisor.config import get_settings


def test_notifications_manual_migration_upgrade_and_downgrade(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SECGUARD_STORAGE_DIR", str(tmp_path / "storage"))
    get_settings.cache_clear()
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{tmp_path / 'storage' / 'secguard.sqlite3'}")
    tables = set(inspect(engine).get_table_names())
    assert {
        "contact_channels",
        "contact_case_links",
        "contact_verification_challenges",
        "report_confirmations",
        "notification_events",
        "notification_components",
        "notification_attempts",
    } <= tables
    challenge_columns = {
        column["name"] for column in inspect(engine).get_columns("contact_verification_challenges")
    }
    assert {"code_sha256", "expires_at", "attempts", "consumed_at"} <= challenge_columns
    event_columns = {
        column["name"] for column in inspect(engine).get_columns("notification_events")
    }
    assert {"idempotency_key", "manifest_sha256", "status", "confirmation_id"} <= event_columns
    engine.dispose()

    command.downgrade(config, "e2f3a4b5c6d7")
    engine = create_engine(f"sqlite:///{tmp_path / 'storage' / 'secguard.sqlite3'}")
    tables = set(inspect(engine).get_table_names())
    assert "contact_channels" not in tables
    assert "notification_events" not in tables
    engine.dispose()
    get_settings.cache_clear()
