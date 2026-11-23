"""Importa el informe congelado de evaluación 005 a la base local.

Uso:
    uv run python scripts/import_evaluation_005.py
    uv run python scripts/import_evaluation_005.py --storage-dir storage/demo
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from secguard_advisor.ai_usage.evaluation_import import import_evaluation
from secguard_advisor.config import Settings
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evidence-dir",
        type=Path,
        default=Path("docs/evidencia/005-evaluacion-proveedores"),
    )
    parser.add_argument("--storage-dir", type=Path, default=None)
    args = parser.parse_args()
    if args.storage_dir is not None:
        settings = Settings(_env_file=None, storage_dir=args.storage_dir)
    else:
        settings = Settings()
    engine = create_engine_for_url(settings.database_url)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            report = import_evaluation(session, args.evidence_dir)
            session.commit()
    finally:
        engine.dispose()
    print(
        json.dumps(
            {
                "evaluation_id": report.evaluation_id,
                "created": report.created,
                "updated": report.updated,
                "providers": list(report.providers),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
