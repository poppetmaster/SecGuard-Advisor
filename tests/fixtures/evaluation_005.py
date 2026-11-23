"""Conjunto congelado de los 10 escenarios de evaluación 005."""

from __future__ import annotations

import hashlib
import json

FROZEN_AT = "2026-11-23"
VERSION = "005-evaluation-v1"

# Documentos ficticios del caso; no contienen datos del usuario.
CASE_DOCUMENTS = (
    {
        "title": "Política de respaldo",
        "text": (
            "# Política de respaldo\n\n"
            "La organización realiza copias de seguridad cifradas cada 24 horas y prueba la "
            "restauración trimestralmente. El responsable de infraestructura conserva el registro "
            "de cada prueba. Las copias se almacenan fuera del sitio."
        ),
    },
    {
        "title": "Gestión de accesos",
        "text": (
            "# Gestión de accesos\n\n"
            "El acceso remoto exige autenticación multifactor. Los permisos se revisan cada "
            "trimestre y el acceso de proveedores requiere aprobación del responsable y registro "
            "de sesión. Las cuentas inactivas se deshabilitan a los 30 días."
        ),
    },
    {
        "title": "Gestión de parches",
        "text": (
            "# Gestión de parches\n\n"
            "Las actualizaciones críticas se aplican en un plazo máximo de siete días. El "
            "inventario de activos identifica propietario y criticidad de cada servicio. Las "
            "ventanas de mantenimiento se registran antes de aplicar cambios."
        ),
    },
)

SYNTHETIC_FINDINGS = (
    ("api-gateway", "High", "900001", ["CVE-2024-0001"]),
    ("api-gateway", "High", "900002", []),
    ("api-gateway", "Low", "900003", []),
    ("customer-portal", "High", "900004", []),
    ("customer-portal", "Medium", "900005", []),
    ("internal-wiki", "Low", "900006", []),
)

SCENARIOS = (
    {
        "id": "S01",
        "kind": "public_csf",
        "question": (
            "¿Cuáles son las seis funciones centrales del NIST Cybersecurity Framework 2.0?"
        ),
        "expected": {"keywords": ["govern", "identify", "protect", "detect", "respond", "recover"]},
        "expected_sources": ["csf2"],
        "case_documents": False,
        "findings": False,
        "approval": "answered; cita resoluble; seis funciones presentes",
    },
    {
        "id": "S02",
        "kind": "public_airmf",
        "question": "¿Cuáles son las funciones centrales del NIST AI Risk Management Framework?",
        "expected": {"keywords": ["govern", "map", "measure", "manage"]},
        "expected_sources": ["airmf"],
        "case_documents": False,
        "findings": False,
        "approval": "answered; cita resoluble; cuatro funciones presentes",
    },
    {
        "id": "S03",
        "kind": "public_owasp",
        "question": (
            "¿Qué riesgos de aplicaciones con LLM describe OWASP y qué controles recomienda? "
            "Mencioná al menos dos riesgos y una recomendación."
        ),
        "expected": {"keywords": ["prompt injection", "sensitive information", "supply chain"]},
        "expected_sources": ["owasp-llm-2025"],
        "case_documents": False,
        "findings": False,
        "approval": "answered; cita resoluble; al menos dos riesgos y una recomendación",
    },
    {
        "id": "S04",
        "kind": "public_combined",
        "question": (
            "¿Cómo se relacionan las funciones del NIST CSF 2.0 con las funciones del NIST AI RMF "
            "para gobernar riesgos de IA? Citá ambas fuentes."
        ),
        "expected": {"keywords": ["govern", "identify", "map", "measure", "manage"]},
        "expected_sources": ["csf2", "airmf"],
        "case_documents": False,
        "findings": False,
        "approval": "answered; citas de ambas fuentes",
    },
    {
        "id": "S05",
        "kind": "case_policy",
        "question": (
            "¿Cada cuánto se prueba la restauración del respaldo y quién conserva el registro?"
        ),
        "expected": {"keywords": ["trimestral", "responsable de infraestructura", "registro"]},
        "expected_sources": ["Política de respaldo"],
        "case_documents": True,
        "findings": False,
        "approval": "answered; cita de la política ficticia; ambos hechos",
    },
    {
        "id": "S06",
        "kind": "case_followup",
        "question": "¿Qué se conserva de cada prueba de restauración?",
        "expected": {"keywords": ["registro", "prueba", "trimestral"]},
        "expected_sources": ["Política de respaldo"],
        "case_documents": True,
        "findings": False,
        "follow_up_of": "S05",
        "approval": "answered; usa el contexto de S05; cita resoluble",
    },
    {
        "id": "S07",
        "kind": "findings_synthetic",
        "question": "¿Cuántos hallazgos High hay por activo en el caso?",
        "expected": {"sql": "synthetic_high_by_asset"},
        "expected_sources": [],
        "case_documents": True,
        "findings": True,
        "approval": "answered; tool ok; total y grupos coinciden con SQLite",
    },
    {
        "id": "S08",
        "kind": "findings_imported",
        "question": (
            "¿Cuántos registros importados tienen severidad 5 y explotabilidad positiva, "
            "agrupados por activo?"
        ),
        "expected": {"sql": "imported_sev5_exploit_positive_by_asset"},
        "expected_sources": [],
        "case_documents": True,
        "findings": True,
        "approval": "Ollama: tool ok y coincide con SQLite; externos: bloqueado por política",
    },
    {
        "id": "S09",
        "kind": "abstention",
        "question": "¿Cuál es la capital de Francia?",
        "expected": {"abstention": True},
        "expected_sources": [],
        "case_documents": False,
        "findings": False,
        "approval": "abstención explícita; sin citas inventadas",
    },
    {
        "id": "S10",
        "kind": "report",
        "question": (
            "Prepará un informe breve sobre los controles de respaldo y acceso del caso: "
            "resumen, evidencias, tres recomendaciones ordenadas y limitaciones."
        ),
        "expected": {"keywords": ["respaldo", "acceso", "recomend", "limit"]},
        "expected_sources": ["Política de respaldo", "Gestión de accesos"],
        "case_documents": True,
        "findings": False,
        "approval": "estructura válida; al menos una cita; recomendaciones y limitaciones",
    },
)


def dataset_payload() -> dict:
    return {
        "version": VERSION,
        "frozen_at": FROZEN_AT,
        "documents": list(CASE_DOCUMENTS),
        "synthetic_findings": [list(item) for item in SYNTHETIC_FINDINGS],
        "scenarios": list(SCENARIOS),
    }


def dataset_sha256() -> str:
    material = json.dumps(
        dataset_payload(), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(material).hexdigest()
