"""Gestión local de autorizaciones de procesamiento externo (005).

No imprime credenciales ni contenido del caso. No envía datos a proveedores.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from secguard_advisor.cases.external import (
    ALLOWED_SCOPES,
    active_authorization,
    authorize_case,
    revoke_case,
)
from secguard_advisor.config import Settings
from secguard_advisor.db.engine import create_engine_for_settings, create_session_factory


def _settings(storage: Path | None) -> Settings:
    if storage is None:
        return Settings()
    return Settings(_env_file=None, storage_dir=storage)


def _serialize(item) -> dict:
    return {
        "id": item.id,
        "case_id": item.case_id,
        "scope": item.scope,
        "policy_version": item.policy_version,
        "authorized_by": item.authorized_by,
        "authorized_at": item.authorized_at,
        "revoked_at": item.revoked_at,
        "note": item.note,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Autorización externa por caso (005)")
    parser.add_argument("--storage", type=Path, default=None)
    parser.add_argument("--case", default=None, help="Identificador del caso")
    parser.add_argument("--scope", choices=ALLOWED_SCOPES, default="fictional_case")
    parser.add_argument("--authorized-by", default=None, help="Identidad declarada")
    parser.add_argument("--note", default=None)
    parser.add_argument("--revoke", action="store_true")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    settings = _settings(args.storage)
    settings.ensure_directories()
    engine = create_engine_for_settings(settings)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            if args.list:
                if args.case:
                    item = active_authorization(session, case_id=args.case)
                    payload = _serialize(item) if item else None
                else:
                    payload = {"error": "Usá --case para listar una autorización."}
                print(json.dumps(payload, ensure_ascii=False))
                return 0
            if not args.case:
                print("Falta --case.", file=sys.stderr)
                return 2
            if args.revoke:
                count = revoke_case(session, case_id=args.case)
                session.commit()
                print(json.dumps({"revoked": count}, ensure_ascii=False))
                return 0
            if not args.authorized_by:
                print("Falta --authorized-by.", file=sys.stderr)
                return 2
            item = authorize_case(
                session,
                case_id=args.case,
                scope=args.scope,
                authorized_by=args.authorized_by,
                note=args.note,
            )
            session.commit()
            print(json.dumps(_serialize(item), ensure_ascii=False))
            return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
