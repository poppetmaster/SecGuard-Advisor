"""Descarga y verifica el corpus oficial."""

import argparse
import sys

from secguard_advisor.config import get_settings
from secguard_advisor.corpus.acquire import acquire_corpus


def main() -> int:
    parser = argparse.ArgumentParser(description="Adquiere el corpus oficial.")
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Solo verifica los originales y el manifiesto existentes.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Fuerza una nueva descarga aunque el original local coincida.",
    )
    args = parser.parse_args()

    settings = get_settings()
    report = acquire_corpus(
        settings,
        verify_only=args.verify_only,
        force_refresh=args.refresh,
    )

    for source in report.sources:
        print(
            f"{source['id']}: {source['status']} "
            f"sha256={source.get('sha256')} pages={source.get('page_count')} "
            f"{source.get('notes') or ''}"
        )

    if report.failed:
        print(f"Fuentes fallidas: {report.failed}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
