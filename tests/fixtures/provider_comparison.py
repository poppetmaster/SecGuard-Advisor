"""Conjunto congelado de comparación de proveedores (005, T035).

Las preguntas y expectativas se fijan antes de medir. El corpus es ficticio para
evitar datos privados. No se usa para responder consultas del producto.
"""

from __future__ import annotations

import hashlib
import json

FROZEN_AT = "2026-11-22"
DATASET_VERSION = "005-comparison-v1"
DOCUMENTS = (
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

QUESTIONS = (
    {
        "id": "q01",
        "question": "¿Cada cuánto se prueba la restauración del respaldo?",
        "expected_title": "Política de respaldo",
        "must_cite": True,
        "expect_abstention": False,
    },
    {
        "id": "q02",
        "question": "¿Con qué frecuencia se realizan las copias de seguridad?",
        "expected_title": "Política de respaldo",
        "must_cite": True,
        "expect_abstention": False,
    },
    {
        "id": "q03",
        "question": "¿Dónde se almacenan las copias de seguridad?",
        "expected_title": "Política de respaldo",
        "must_cite": True,
        "expect_abstention": False,
    },
    {
        "id": "q04",
        "question": "¿Qué autenticación exige el acceso remoto?",
        "expected_title": "Gestión de accesos",
        "must_cite": True,
        "expect_abstention": False,
    },
    {
        "id": "q05",
        "question": "¿Cada cuánto se revisan los permisos?",
        "expected_title": "Gestión de accesos",
        "must_cite": True,
        "expect_abstention": False,
    },
    {
        "id": "q06",
        "question": "¿Qué requisitos tiene el acceso de proveedores?",
        "expected_title": "Gestión de accesos",
        "must_cite": True,
        "expect_abstention": False,
    },
    {
        "id": "q07",
        "question": "¿En qué plazo se aplican las actualizaciones críticas?",
        "expected_title": "Gestión de parches",
        "must_cite": True,
        "expect_abstention": False,
    },
    {
        "id": "q08",
        "question": "¿Qué identifica el inventario de activos?",
        "expected_title": "Gestión de parches",
        "must_cite": True,
        "expect_abstention": False,
    },
    {
        "id": "q09",
        "question": "¿Cuál es la capital de Francia?",
        "expected_title": None,
        "must_cite": False,
        "expect_abstention": True,
    },
    {
        "id": "q10",
        "question": "¿Qué receta de cocina recomienda el documento?",
        "expected_title": None,
        "must_cite": False,
        "expect_abstention": True,
    },
)


def dataset_payload() -> dict:
    return {
        "version": DATASET_VERSION,
        "frozen_at": FROZEN_AT,
        "documents": list(DOCUMENTS),
        "questions": list(QUESTIONS),
    }


def dataset_sha256() -> str:
    material = json.dumps(
        dataset_payload(), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(material).hexdigest()
