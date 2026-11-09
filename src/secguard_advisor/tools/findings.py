"""Herramienta de lectura de hallazgos sintéticos con alcance en clausura."""

from __future__ import annotations

from time import perf_counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import case, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.db.models import Asset, Finding, FindingCve, SyntheticDataset

TOOL_NAME = "findings_query"
SEVERITY_ORDER = ("Critical", "High", "Medium", "Low", "Info")
DEFAULT_LIMIT = 20
MAX_LIMIT = 100


class ToolArgumentError(Exception):
    """Argumentos inválidos: el modelo puede corregir dentro del límite."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        self.message = message or "Los argumentos de findings_query no son válidos."
        super().__init__(self.message)


class ToolExecutionError(RuntimeError):
    """Fallo de base de datos al consultar hallazgos."""


class ToolTimeout(RuntimeError):
    """La consulta de hallazgos excedió su tiempo."""


class FindingsArguments(BaseModel):
    """Esquema estricto y sin `case_id` para la herramienta."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    asset: str | None = Field(default=None, max_length=120)
    severity: Literal["Critical", "High", "Medium", "Low", "Info"] | None = None
    qid: str | None = Field(default=None, pattern=r"^[0-9]{1,10}$")
    cve: str | None = Field(default=None, pattern=r"^CVE-[0-9]{4}-[0-9]{4,7}$")
    group_by: Literal["severity", "asset"] | None = None
    detail: bool = False
    limit: int = Field(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)


def _translate(error: ValidationError) -> ToolArgumentError:
    first = error.errors()[0]
    field = str(first.get("loc", ("",))[0])
    code = {
        "severity": "invalid_severity",
        "qid": "invalid_qid",
        "cve": "invalid_cve",
        "limit": "limit_out_of_range",
    }.get(field, "invalid_arguments")
    return ToolArgumentError(code)


def parse_arguments(arguments: dict) -> FindingsArguments:
    """Valida el objeto recibido del modelo contra el esquema estricto."""
    try:
        return FindingsArguments.model_validate(arguments)
    except ValidationError as exc:
        raise _translate(exc) from exc


class FindingsQuery:
    """Consulta de hallazgos limitada al caso capturado en el constructor."""

    def __init__(
        self,
        factory: sessionmaker[Session],
        scope: CaseScope,
        *,
        timeout_seconds: float = 5.0,
    ) -> None:
        self._factory = factory
        self._scope = scope
        self._timeout = timeout_seconds

    def execute(self, arguments: dict) -> dict:
        """Valida, consulta y devuelve el resultado del contrato."""
        started = perf_counter()
        parsed = parse_arguments(arguments)
        try:
            with self._factory() as session:
                result = self._run(session, parsed)
        except SQLAlchemyError as exc:
            raise ToolExecutionError("No se pudieron consultar los hallazgos del caso.") from exc
        if perf_counter() - started > self._timeout:
            raise ToolTimeout("La consulta de hallazgos excedió el tiempo permitido.")
        return result

    def _filters(self, arguments: FindingsArguments) -> list:
        filters = [Finding.case_id == self._scope.case_id]
        if arguments.asset is not None:
            filters.append(
                Finding.asset_id.in_(
                    select(Asset.id).where(
                        Asset.case_id == self._scope.case_id,
                        Asset.name == arguments.asset,
                    )
                )
            )
        if arguments.severity is not None:
            filters.append(Finding.severity_label == arguments.severity)
        if arguments.qid is not None:
            filters.append(Finding.qid == arguments.qid)
        if arguments.cve is not None:
            # Subconsulta: un hallazgo con varios CVE no multiplica filas.
            filters.append(
                Finding.id.in_(select(FindingCve.finding_id).where(FindingCve.cve == arguments.cve))
            )
        return filters

    def _groups(self, session: Session, arguments: FindingsArguments, filters: list) -> list:
        if arguments.group_by == "asset":
            rows = session.execute(
                select(Asset.name, func.count())
                .select_from(Finding)
                .join(Asset, Finding.asset_id == Asset.id)
                .where(*filters)
                .group_by(Asset.name)
                .order_by(Asset.name)
            ).all()
            return [{"key": name, "count": count} for name, count in rows]

        severity_rank = case(
            {label: index for index, label in enumerate(SEVERITY_ORDER)},
            value=Finding.severity_label,
            else_=len(SEVERITY_ORDER),
        )
        rows = session.execute(
            select(Finding.severity_label, func.count())
            .where(*filters)
            .group_by(Finding.severity_label)
            .order_by(severity_rank)
        ).all()
        return [{"key": label, "count": count} for label, count in rows]

    def _dataset(self, session: Session, filters: list) -> dict:
        dataset = session.scalar(
            select(SyntheticDataset)
            .join(Finding, Finding.dataset_id == SyntheticDataset.id)
            .where(*filters)
            .order_by(SyntheticDataset.name)
            .limit(1)
        )
        if dataset is None:
            return {
                "name": None,
                "version": None,
                "checksum": None,
                "is_synthetic": True,
            }
        return {
            "name": dataset.name,
            "version": dataset.version,
            "checksum": dataset.checksum,
            "is_synthetic": True,
        }

    def _items(self, session: Session, arguments: FindingsArguments, filters: list) -> list[dict]:
        severity_rank = case(
            {label: index for index, label in enumerate(SEVERITY_ORDER)},
            value=Finding.severity_label,
            else_=len(SEVERITY_ORDER),
        )
        rows = session.execute(
            select(Finding, Asset.name)
            .join(Asset, Finding.asset_id == Asset.id)
            .where(*filters)
            .order_by(severity_rank, Asset.name, Finding.id)
            .limit(arguments.limit)
        ).all()
        finding_ids = [finding.id for finding, _asset in rows]
        cves: dict[str, list[str]] = {finding_id: [] for finding_id in finding_ids}
        if finding_ids:
            for finding_id, cve in session.execute(
                select(FindingCve.finding_id, FindingCve.cve)
                .where(FindingCve.finding_id.in_(finding_ids))
                .order_by(FindingCve.cve)
            ).all():
                cves[finding_id].append(cve)
        return [
            {
                "finding_id": finding.id,
                "asset": asset_name,
                "title": finding.title,
                "severity_label": finding.severity_label,
                "severity_raw": finding.severity_raw,
                "cvss_base": finding.cvss_base,
                "qid": finding.qid,
                "cves": cves[finding.id],
                "first_detected": finding.first_detected,
                "last_detected": finding.last_detected,
                "provenance": finding.provenance,
            }
            for finding, asset_name in rows
        ]

    def _run(self, session: Session, arguments: FindingsArguments) -> dict:
        filters = self._filters(arguments)
        total = session.scalar(select(func.count()).select_from(Finding).where(*filters)) or 0
        result = {
            "total": total,
            "groups": self._groups(session, arguments, filters),
            "dataset": self._dataset(session, filters),
            "truncated": False,
        }
        if arguments.detail:
            items = self._items(session, arguments, filters)
            result["items"] = items
            result["truncated"] = total > len(items)
        return result
