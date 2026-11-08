"""Dataset sintético determinista para la demostración."""

import hashlib
import json
import random
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from secguard_advisor.db.models import (
    Asset,
    Case,
    Finding,
    SyntheticDataset,
)

DEMO_TITLE = "Evaluación de un asistente interno de IA"
DEMO_NOTICE = (
    "Escenario educativo sintético. No corresponde a una empresa real ni a una "
    "importación de Qualys."
)
DEMO_DATASET_NAME = "demo-findings"
DEMO_DATASET_VERSION = "1"
DEMO_SEED = 42
DEMO_PROVENANCE = "synthetic:demo-findings-v1"

_ASSETS = (
    ("api-gateway", "Puerta de enlace de APIs interna"),
    ("customer-portal", "Portal de clientes"),
    ("internal-wiki", "Wiki interna de conocimiento"),
)

_TEMPLATES = (
    ("api-gateway", "Componente desactualizado", "5", "Critical", 9.8, "900001"),
    ("api-gateway", "Configuración TLS débil", "4", "High", 7.5, "900002"),
    ("api-gateway", "Cabeceras de seguridad ausentes", "3", "Medium", 5.3, "900003"),
    ("customer-portal", "Permisos excesivos de cuenta", "4", "High", 8.1, "900004"),
    ("customer-portal", "Mensajes de error con información interna", "2", "Low", 3.1, "900005"),
    ("customer-portal", "Dependencia con vulnerabilidad conocida", "5", "Critical", 9.1, "900006"),
    ("internal-wiki", "Control de acceso inconsistente", "4", "High", 7.2, "900007"),
    ("internal-wiki", "Registro de auditoría incompleto", "3", "Medium", 4.8, "900008"),
    (
        "internal-wiki",
        "Contraseña por defecto en servicio auxiliar",
        "5",
        "Critical",
        9.4,
        "900009",
    ),
    ("api-gateway", "Puerto de administración expuesto", "4", "High", 8.0, "900010"),
    ("customer-portal", "Validación de entrada insuficiente", "3", "Medium", 6.1, "900011"),
    ("internal-wiki", "Certificado próximo a vencer", "1", "Info", 0.0, "900012"),
)


@dataclass(frozen=True, slots=True)
class DemoAsset:
    name: str
    description: str


@dataclass(frozen=True, slots=True)
class DemoFinding:
    asset: str
    title: str
    severity_raw: str
    severity_label: str
    cvss_base: float | None
    qid: str
    first_detected: str
    last_detected: str


@dataclass(frozen=True, slots=True)
class DemoDataset:
    name: str
    version: str
    seed: int
    checksum: str
    assets: tuple[DemoAsset, ...]
    findings: tuple[DemoFinding, ...]

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "seed": self.seed,
            "assets": [
                {"name": asset.name, "description": asset.description} for asset in self.assets
            ],
            "findings": [
                {
                    "asset": finding.asset,
                    "title": finding.title,
                    "severity_raw": finding.severity_raw,
                    "severity_label": finding.severity_label,
                    "cvss_base": finding.cvss_base,
                    "qid": finding.qid,
                    "first_detected": finding.first_detected,
                    "last_detected": finding.last_detected,
                }
                for finding in self.findings
            ],
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.as_dict(),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )


@dataclass(frozen=True, slots=True)
class SeedReport:
    created: bool
    case_id: str
    assets: int
    findings: int
    checksum: str


class SeedConflictError(RuntimeError):
    """El dataset existente no coincide con el esperado."""


def build_demo_dataset(seed: int = DEMO_SEED) -> DemoDataset:
    """Construye el dataset determinista a partir de la semilla."""
    rng = random.Random(seed)
    ordered = list(_TEMPLATES)
    rng.shuffle(ordered)
    base_date = date(2026, 1, 1)

    findings: list[DemoFinding] = []
    for asset, title, raw, label, cvss, qid in ordered:
        first = base_date + timedelta(days=rng.randint(0, 60))
        last = first + timedelta(days=rng.randint(1, 30))
        findings.append(
            DemoFinding(
                asset=asset,
                title=title,
                severity_raw=raw,
                severity_label=label,
                cvss_base=cvss,
                qid=qid,
                first_detected=first.isoformat(),
                last_detected=last.isoformat(),
            )
        )

    dataset = DemoDataset(
        name=DEMO_DATASET_NAME,
        version=DEMO_DATASET_VERSION,
        seed=seed,
        checksum="",
        assets=tuple(DemoAsset(name=name, description=desc) for name, desc in _ASSETS),
        findings=tuple(findings),
    )
    checksum = hashlib.sha256(dataset.canonical_json().encode("utf-8")).hexdigest()
    return DemoDataset(
        name=dataset.name,
        version=dataset.version,
        seed=dataset.seed,
        checksum=checksum,
        assets=dataset.assets,
        findings=dataset.findings,
    )


def _existing_dataset(session: Session) -> SyntheticDataset | None:
    return session.scalar(
        select(SyntheticDataset).where(SyntheticDataset.name == DEMO_DATASET_NAME)
    )


def seed_demo(session: Session) -> SeedReport:
    """Carga el dataset en el caso de demostración de forma idempotente."""
    dataset = build_demo_dataset()
    existing = _existing_dataset(session)

    if existing is not None:
        if existing.checksum != dataset.checksum:
            raise SeedConflictError(
                "El dataset de demostración cambió; se requiere una versión nueva."
            )
        case_id = existing.applies_to_case_id or ""
        return SeedReport(
            created=False,
            case_id=case_id,
            assets=session.scalar(
                select(func.count()).select_from(Asset).where(Asset.case_id == case_id)
            )
            or 0,
            findings=session.scalar(
                select(func.count()).select_from(Finding).where(Finding.case_id == case_id)
            )
            or 0,
            checksum=dataset.checksum,
        )

    case = session.scalar(select(Case).where(Case.title == DEMO_TITLE))
    if case is None:
        case = Case(
            title=DEMO_TITLE,
            description="Caso de demostración para el recorrido educativo.",
            ai_application="Asistente interno de consulta documental",
            data_processed="Documentación pública y evidencias sintéticas",
            restrictions="Sin datos de una organización real",
            context_is_synthetic=True,
            synthetic_notice=DEMO_NOTICE,
        )
        session.add(case)
        session.flush()
    elif not case.context_is_synthetic:
        raise SeedConflictError("Existe un caso con el título de demostración que no es sintético.")

    assets: dict[str, Asset] = {}
    for asset_spec in dataset.assets:
        asset = session.scalar(
            select(Asset).where(Asset.case_id == case.id, Asset.name == asset_spec.name)
        )
        if asset is None:
            asset = Asset(
                case_id=case.id,
                name=asset_spec.name,
                description=asset_spec.description,
            )
            session.add(asset)
            session.flush()
        assets[asset_spec.name] = asset

    stored_dataset = SyntheticDataset(
        name=dataset.name,
        version=dataset.version,
        seed=dataset.seed,
        checksum=dataset.checksum,
        applies_to_case_id=case.id,
        description="Hallazgos educativos sintéticos para la demostración.",
    )
    session.add(stored_dataset)
    session.flush()

    for finding_spec in dataset.findings:
        session.add(
            Finding(
                case_id=case.id,
                asset_id=assets[finding_spec.asset].id,
                dataset_id=stored_dataset.id,
                title=finding_spec.title,
                severity_raw=finding_spec.severity_raw,
                severity_label=finding_spec.severity_label,
                cvss_base=finding_spec.cvss_base,
                qid=finding_spec.qid,
                first_detected=finding_spec.first_detected,
                last_detected=finding_spec.last_detected,
                provenance=DEMO_PROVENANCE,
                is_synthetic=True,
            )
        )

    session.commit()
    return SeedReport(
        created=True,
        case_id=case.id,
        assets=len(assets),
        findings=len(dataset.findings),
        checksum=dataset.checksum,
    )
