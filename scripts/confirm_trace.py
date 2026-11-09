"""Confirma por API de lectura que una traza observada corresponde a una ejecución."""

from __future__ import annotations

import argparse
import json
import os

from secguard_advisor.config import get_settings
from secguard_advisor.db.engine import create_engine_for_settings, create_session_factory
from secguard_advisor.evidence.confirm import ConfirmationError, confirm_trace


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Confirma una traza de LangSmith contra la ejecución local."
    )
    parser.add_argument("--run-id", required=True, help="Identificador local de la ejecución.")
    parser.add_argument("--trace-id", required=True, help="Identificador de la traza en LangSmith.")
    parser.add_argument(
        "--reviewer",
        default=os.environ.get("SECGUARD_REVIEWER_NAME", ""),
        help="Identidad declarada de quien confirma; por defecto SECGUARD_REVIEWER_NAME.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    settings = get_settings()
    settings.ensure_directories()
    engine = create_engine_for_settings(settings)
    factory = create_session_factory(engine)
    try:
        result = confirm_trace(
            factory,
            settings,
            run_id=args.run_id,
            trace_id=args.trace_id,
            reviewer=args.reviewer,
        )
    except ConfirmationError as exc:
        print(
            json.dumps(
                {
                    "status": "rejected",
                    "code": exc.code,
                    "message": str(exc),
                    "run_id": args.run_id,
                    "trace_id": args.trace_id,
                },
                ensure_ascii=False,
            )
        )
        return 2 if exc.code in {"api_unavailable", "credentials_missing"} else 1
    finally:
        engine.dispose()

    print(
        json.dumps(
            {
                "status": result.status,
                "run_id": result.run_id,
                "trace_id": result.trace_id,
                "project": result.project,
                "reviewer": result.reviewer,
                "confirmed_at": result.confirmed_at,
                "trace_name": result.trace_name,
                "trace_started_at": result.trace_started_at,
                "trace_url": result.trace_url,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
