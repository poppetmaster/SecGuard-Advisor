"""Motor y fábrica de sesiones de SQLite."""

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from secguard_advisor.config import Settings


def _configure_sqlite(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def create_engine_for_url(url: str) -> Engine:
    """Crea un motor SQLite con los PRAGMA del proyecto."""
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False, "timeout": 5},
    )
    event.listen(engine, "connect", _configure_sqlite)
    return engine


def create_engine_for_settings(settings: Settings) -> Engine:
    """Crea el motor del almacenamiento configurado."""
    settings.ensure_directories()
    return create_engine_for_url(settings.database_url)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Devuelve la fábrica de sesiones de la aplicación."""
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
