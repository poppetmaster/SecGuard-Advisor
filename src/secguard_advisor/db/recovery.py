"""Reconciliación de estado al arrancar la aplicación."""

from dataclasses import dataclass

from sqlalchemy import update
from sqlalchemy.orm import Session

from secguard_advisor.db.models import (
    DocumentVersion,
    IngestionJob,
    Run,
    utc_now_iso,
)


@dataclass(frozen=True, slots=True)
class RecoveryReport:
    """Conteo de operaciones reconciliadas."""

    runs: int
    ingestion_jobs: int
    document_versions: int


def reconcile_startup(session: Session) -> RecoveryReport:
    """Marca como interrumpidas las operaciones que quedaron abiertas."""
    now = utc_now_iso()

    runs = session.execute(
        update(Run)
        .where(Run.status == "running")
        .values(
            status="interrupted",
            finished_at=now,
            error_code="interrupted",
            error_message="El proceso se reinició durante la ejecución.",
        )
    ).rowcount

    jobs = session.execute(
        update(IngestionJob)
        .where(IngestionJob.status == "running")
        .values(
            status="interrupted",
            finished_at=now,
            error_code="interrupted",
            error_message="El proceso se reinició durante la ingesta.",
        )
    ).rowcount

    versions = session.execute(
        update(DocumentVersion)
        .where(DocumentVersion.status == "processing")
        .values(
            status="failed",
            error_code="interrupted",
            error_message="La ingesta se interrumpió y debe reintentarse.",
            superseded_at=None,
        )
    ).rowcount

    session.commit()
    session.expire_all()
    return RecoveryReport(
        runs=runs,
        ingestion_jobs=jobs,
        document_versions=versions,
    )
