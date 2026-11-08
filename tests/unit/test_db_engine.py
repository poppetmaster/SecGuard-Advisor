"""Pruebas del motor SQLite y de la fábrica de sesiones."""

from pathlib import Path

from sqlalchemy import text

from secguard_advisor.db.engine import create_engine_for_url, create_session_factory


def test_sqlite_pragmas_and_session(tmp_path: Path) -> None:
    engine = create_engine_for_url(f"sqlite:///{tmp_path / 'test.sqlite3'}")

    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 1
        assert connection.execute(text("PRAGMA journal_mode")).scalar().lower() == "wal"
        assert connection.execute(text("PRAGMA busy_timeout")).scalar() == 5000

    factory = create_session_factory(engine)
    with factory() as session:
        assert session.execute(text("SELECT 1")).scalar() == 1

    engine.dispose()
