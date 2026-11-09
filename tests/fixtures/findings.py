"""Datos sintéticos de hallazgos para pruebas."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from secguard_advisor.db.models import (
    Asset,
    Case,
    Finding,
    FindingCve,
    SyntheticDataset,
    new_id,
)
from secguard_advisor.seed.demo import build_demo_dataset


@dataclass(frozen=True, slots=True)
class SeededFinding:
    id: str
    asset: str
    severity: str
    qid: str
    cves: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SeededFindings:
    case_id: str
    dataset_name: str
    dataset_version: str
    dataset_checksum: str
    findings: tuple[SeededFinding, ...]


def _dataset(session: Session, case_id: str, version: str = "1") -> SyntheticDataset:
    demo = build_demo_dataset()
    dataset = SyntheticDataset(
        name=f"demo-findings-{case_id[:6]}",
        version=version,
        seed=demo.seed,
        checksum=demo.checksum,
        applies_to_case_id=case_id,
        description="Datos educativos sintéticos",
    )
    session.add(dataset)
    session.flush()
    return dataset


def seed_findings(
    factory: sessionmaker[Session],
    *,
    title: str = "Caso con hallazgos",
    findings: list[tuple[str, str, str, list[str]]],
    case_id: str | None = None,
    assets: list[str] | None = None,
) -> SeededFindings:
    """Crea caso, activos, dataset y hallazgos; ``findings`` es (asset, severidad, qid, cves)."""
    with factory() as session:
        if case_id is None:
            case = Case(title=title, synthetic_notice="Escenario educativo sintético")
            session.add(case)
            session.flush()
            resolved_case_id = case.id
        else:
            resolved_case_id = case_id
            case = session.get(Case, case_id)
            if case is None:
                raise LookupError(case_id)
        asset_names = assets or sorted({item[0] for item in findings})
        asset_rows = {}
        for name in asset_names:
            asset = Asset(case_id=case.id, name=name, description=f"Activo {name}")
            session.add(asset)
            session.flush()
            asset_rows[name] = asset
        dataset = _dataset(session, resolved_case_id)
        created: list[SeededFinding] = []
        for asset_name, severity, qid, cves in findings:
            finding = Finding(
                id=new_id(),
                case_id=resolved_case_id,
                asset_id=asset_rows[asset_name].id,
                dataset_id=dataset.id,
                title=f"Hallazgo {qid}",
                severity_raw={
                    "Critical": "5",
                    "High": "4",
                    "Medium": "3",
                    "Low": "2",
                    "Info": "1",
                }[severity],
                severity_label=severity,
                cvss_base=None if severity == "Info" else 7.5,
                qid=qid,
                first_detected="2026-01-10",
                last_detected="2026-02-01",
                provenance="synthetic:demo-findings-v1",
                is_synthetic=True,
            )
            session.add(finding)
            session.flush()
            for cve in cves:
                session.add(FindingCve(finding_id=finding.id, cve=cve))
            created.append(
                SeededFinding(
                    id=finding.id,
                    asset=asset_name,
                    severity=severity,
                    qid=qid,
                    cves=tuple(cves),
                )
            )
        session.commit()
        return SeededFindings(
            case_id=resolved_case_id,
            dataset_name=dataset.name,
            dataset_version=dataset.version,
            dataset_checksum=dataset.checksum,
            findings=tuple(created),
        )


def seed_empty_case(factory: sessionmaker[Session], title: str = "Caso sin hallazgos") -> str:
    with factory() as session:
        case = Case(title=title, synthetic_notice="Escenario educativo sintético")
        session.add(case)
        session.commit()
        return case.id


def demo_storage(tmp_path: Path) -> Path:
    return tmp_path / "storage"
