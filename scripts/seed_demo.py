"""Carga el dataset sintético de demostración."""

import sys

from sqlalchemy.exc import OperationalError

from secguard_advisor.config import get_settings
from secguard_advisor.db.engine import create_engine_for_settings, create_session_factory
from secguard_advisor.seed.demo import seed_demo


def main() -> int:
    settings = get_settings()
    settings.ensure_directories()
    engine = create_engine_for_settings(settings)
    try:
        with create_session_factory(engine)() as session:
            report = seed_demo(session)
    except OperationalError:
        print(
            "error: la base no tiene el esquema. Ejecutá `uv run alembic upgrade head`.",
            file=sys.stderr,
        )
        return 2
    finally:
        engine.dispose()

    state = "creado" if report.created else "ya existía"
    print(
        f"seed {state}: case={report.case_id} assets={report.assets} "
        f"findings={report.findings} checksum={report.checksum}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
