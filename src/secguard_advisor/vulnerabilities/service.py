"""Staging, confirmación, cancelación y expiración de importaciones Qualys."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from secguard_advisor.cases.scope import CaseNotFoundError
from secguard_advisor.config import Settings, get_settings
from secguard_advisor.db.models import (
    Case,
    QualysImport,
    QualysImportIssue,
    QualysVulnerability,
    QualysVulnerabilityCve,
    new_id,
    utc_now_iso,
)
from secguard_advisor.vulnerabilities import (
    ADAPTER_VERSION,
    PRIORITY_RULE_VERSION,
    SEVERITY_POLICY_VERSION,
    STATUS_POLICY_VERSION,
)
from secguard_advisor.vulnerabilities.validation import ValidationResult, validate_csv


class QualysServiceError(RuntimeError):
    """Error de dominio del servicio de importación."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class ImportNotFoundError(QualysServiceError):
    """La importación no existe o pertenece a otro caso."""

    def __init__(self) -> None:
        super().__init__("import_not_found", "La importación no existe en este caso.")


class InvalidTransitionError(QualysServiceError):
    """La transición solicitada no es válida."""


@dataclass(frozen=True, slots=True)
class StageResult:
    import_record: QualysImport
    idempotent: bool = False


@dataclass(frozen=True, slots=True)
class ConfirmResult:
    import_record: QualysImport
    idempotent: bool = False


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime) -> str:
    return value.isoformat()


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


class QualysImportService:
    """Servicio local de importaciones; no conoce rutas ni formularios HTTP."""

    def __init__(
        self,
        factory: sessionmaker[Session],
        settings: Settings | None = None,
    ) -> None:
        self._factory = factory
        self._settings = settings or get_settings()

    def stage_import(
        self,
        case_id: str,
        filename: str,
        content: bytes,
        *,
        manifest_path: Path | None = None,
    ) -> StageResult:
        """Valida y persiste una importación staged o rejected."""
        sha = hashlib.sha256(content).hexdigest()
        with self._factory() as session:
            if session.get(Case, case_id) is None:
                raise CaseNotFoundError(case_id)
            self._expire_stale_in_session(session)
            existing = session.scalar(
                select(QualysImport)
                .where(
                    QualysImport.case_id == case_id,
                    QualysImport.csv_sha256 == sha,
                    QualysImport.status == "confirmed",
                )
                .limit(1)
            )
            if existing is not None:
                return StageResult(existing, idempotent=True)
            result = validate_csv(content, settings=self._settings, manifest_path=manifest_path)
            record = self._persist_result(session, case_id, filename, content, sha, result)
            session.commit()
            return StageResult(record, idempotent=False)

    def get_import(self, case_id: str, import_id: str) -> QualysImport:
        with self._factory() as session:
            record = session.get(QualysImport, import_id)
            if record is None or record.case_id != case_id:
                raise ImportNotFoundError()
            return record

    def confirm_import(self, case_id: str, import_id: str) -> ConfirmResult:
        """Confirma solo staged; reintenta de forma segura ante concurrencia."""
        for _ in range(3):
            with self._factory() as session:
                record = session.get(QualysImport, import_id)
                if record is None or record.case_id != case_id:
                    raise ImportNotFoundError()
                if record.status == "confirmed":
                    return ConfirmResult(record, idempotent=True)
                if record.status != "staged":
                    raise InvalidTransitionError(
                        "import_not_staged", "Solo una importación staged puede confirmarse."
                    )
                if record.expires_at is not None and record.expires_at < utc_now_iso():
                    self._mark_expired(session, record)
                    session.commit()
                    raise InvalidTransitionError(
                        "import_expired", "La validación expiró; cargue el archivo de nuevo."
                    )
                maximum = session.scalar(
                    select(func.max(QualysImport.confirmed_sequence)).where(
                        QualysImport.case_id == case_id
                    )
                )
                record.status = "confirmed"
                record.confirmed_at = utc_now_iso()
                record.confirmed_sequence = (maximum or 0) + 1
                record.expires_at = None
                sha = record.csv_sha256
                try:
                    session.commit()
                except IntegrityError:
                    session.rollback()
                    existing = session.scalar(
                        select(QualysImport)
                        .where(
                            QualysImport.case_id == case_id,
                            QualysImport.csv_sha256 == sha,
                            QualysImport.status == "confirmed",
                        )
                        .limit(1)
                    )
                    if existing is not None:
                        return ConfirmResult(existing, idempotent=True)
                    continue
                return ConfirmResult(record, idempotent=False)
        raise InvalidTransitionError(
            "sequence_conflict", "No se pudo asignar la secuencia de confirmación."
        )

    def cancel_import(self, case_id: str, import_id: str) -> QualysImport:
        with self._factory() as session:
            record = session.get(QualysImport, import_id)
            if record is None or record.case_id != case_id:
                raise ImportNotFoundError()
            if record.status == "confirmed":
                raise InvalidTransitionError(
                    "confirmed_immutable", "Una instantánea confirmada no se cancela."
                )
            if record.status not in {"staged", "rejected"}:
                raise InvalidTransitionError(
                    "import_not_cancellable", "La importación no se puede cancelar en este estado."
                )
            record.status = "cancelled"
            record.cancelled_at = utc_now_iso()
            session.execute(
                delete(QualysVulnerability).where(QualysVulnerability.import_id == import_id)
            )
            session.execute(
                delete(QualysImportIssue).where(QualysImportIssue.import_id == import_id)
            )
            session.commit()
            return record

    def expire_stale(self, *, now: datetime | None = None) -> int:
        with self._factory() as session:
            count = self._expire_stale_in_session(session, now=now)
            session.commit()
            return count

    def list_rows(self, case_id: str, import_id: str) -> list[QualysVulnerability]:
        with self._factory() as session:
            record = session.get(QualysImport, import_id)
            if record is None or record.case_id != case_id:
                raise ImportNotFoundError()
            return list(
                session.scalars(
                    select(QualysVulnerability)
                    .where(
                        QualysVulnerability.case_id == case_id,
                        QualysVulnerability.import_id == import_id,
                    )
                    .order_by(QualysVulnerability.row_number)
                )
            )

    def _expire_stale_in_session(self, session: Session, *, now: datetime | None = None) -> int:
        current = _iso(now or _now())
        rows = list(
            session.scalars(
                select(QualysImport).where(
                    QualysImport.status.in_(("staged", "rejected")),
                    QualysImport.expires_at.is_not(None),
                    QualysImport.expires_at < current,
                )
            )
        )
        for record in rows:
            self._mark_expired(session, record)
        return len(rows)

    def _mark_expired(self, session: Session, record: QualysImport) -> None:
        record.status = "expired"
        session.execute(
            delete(QualysVulnerability).where(QualysVulnerability.import_id == record.id)
        )
        session.execute(delete(QualysImportIssue).where(QualysImportIssue.import_id == record.id))

    def _persist_result(
        self,
        session: Session,
        case_id: str,
        filename: str,
        content: bytes,
        sha: str,
        result: ValidationResult,
    ) -> QualysImport:
        now = _now()
        expires = now + timedelta(seconds=self._settings.qualys_staging_ttl_seconds)
        record = QualysImport(
            id=new_id(),
            case_id=case_id,
            status=result.status,
            original_filename=Path(filename).name or "archivo.csv",
            csv_sha256=sha,
            csv_bytes=len(content),
            manifest_sha256=result.manifest.manifest_sha256,
            manifest_status=result.manifest.status,
            row_count=result.row_count,
            valid_rows=result.valid_rows,
            invalid_rows=result.invalid_rows,
            warning_rows=result.warning_rows,
            manual_review_rows=result.manual_review_rows,
            possible_repeat_groups=result.possible_repeat_groups,
            possible_repeat_rows=result.possible_repeat_rows,
            status_counts_json=_json(result.status_counts),
            severity_counts_json=_json(result.severity_counts),
            exploitability_counts_json=_json(result.exploitability_counts),
            malware_counts_json=_json(result.malware_counts),
            priority_counts_json=_json(result.priority_counts),
            summary_json=_json(
                {
                    **result.summary,
                    "manifest_status": result.manifest.status,
                    "adapter_version": ADAPTER_VERSION,
                }
            ),
            adapter_version=ADAPTER_VERSION,
            severity_policy_version=SEVERITY_POLICY_VERSION,
            status_policy_version=STATUS_POLICY_VERSION,
            priority_rule_version=PRIORITY_RULE_VERSION,
            created_at=_iso(now),
            validated_at=_iso(now),
            expires_at=_iso(expires) if result.status in {"staged", "rejected"} else None,
            error_code=result.error_code,
            error_message=result.error_message,
        )
        session.add(record)
        session.flush()
        for issue in result.issues:
            session.add(
                QualysImportIssue(
                    id=new_id(),
                    import_id=record.id,
                    row_number=issue.row_number,
                    severity=issue.severity,
                    code=issue.code,
                    field=issue.field,
                    message=issue.message,
                    created_at=_iso(now),
                )
            )
        if result.status == "staged":
            for row in result.rows:
                vulnerability = QualysVulnerability(
                    id=new_id(),
                    import_id=record.id,
                    case_id=case_id,
                    row_number=row.row_number,
                    raw_json=row.raw_json,
                    asset_label=row.asset_label,
                    ip=row.ip,
                    dns=row.dns,
                    netbios=row.netbios,
                    fqdn=row.fqdn,
                    qid=row.qid,
                    title=row.title,
                    vuln_type=row.vuln_type,
                    status_raw=row.status_raw,
                    status_normalized=row.status_normalized,
                    status_group=row.status_group,
                    severity_raw=row.severity_raw,
                    severity_level=row.severity_level,
                    severity_label=row.severity_label,
                    severity_policy_version=SEVERITY_POLICY_VERSION,
                    port=row.port,
                    protocol=row.protocol,
                    first_detected=row.first_detected,
                    last_detected=row.last_detected,
                    first_detected_normalized=row.first_detected_normalized,
                    last_detected_normalized=row.last_detected_normalized,
                    date_last_fixed=row.date_last_fixed,
                    first_reopened=row.first_reopened,
                    last_reopened=row.last_reopened,
                    times_detected=row.times_detected,
                    times_reopened=row.times_reopened,
                    exploitability_raw=row.exploitability_raw,
                    exploitability_eval=row.exploitability_eval,
                    exploitability_reason=row.exploitability_reason,
                    malware_raw=row.malware_raw,
                    malware_eval=row.malware_eval,
                    malware_reason=row.malware_reason,
                    priority_flag=row.priority_flag,
                    priority_reason=row.priority_reason,
                    priority_rule_version=PRIORITY_RULE_VERSION,
                    vendor_metrics_json=row.vendor_metrics_json,
                    created_at=_iso(now),
                )
                session.add(vulnerability)
                for cve in row.cves:
                    session.add(QualysVulnerabilityCve(vulnerability_id=vulnerability.id, cve=cve))
        session.flush()
        return record
