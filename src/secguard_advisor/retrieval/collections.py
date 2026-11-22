"""Nombres y alcances de las colecciones vectoriales."""

import re
from dataclasses import dataclass

_CASE_ID = re.compile(r"^[0-9a-f]{32}$")
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*[A-Za-z0-9]$")


@dataclass(frozen=True, slots=True)
class CollectionScope:
    kind: str
    case_id: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in {"public", "case"}:
            raise ValueError("Alcance de colección inválido.")
        if self.kind == "public" and self.case_id is not None:
            raise ValueError("El corpus público no tiene caso.")
        if self.kind == "case" and (self.case_id is None or not _CASE_ID.match(self.case_id)):
            raise ValueError("El alcance de caso requiere un identificador válido.")


def public_scope() -> CollectionScope:
    return CollectionScope(kind="public")


def case_scope(case_id: str) -> CollectionScope:
    return CollectionScope(kind="case", case_id=case_id)


def _model_slug(model: str, max_length: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", model.lower()).strip("-")
    return (slug or "model")[:max_length].rstrip("-") or "model"


def validate_collection_name(name: str) -> str:
    if not 3 <= len(name) <= 63:
        raise ValueError("El nombre de la colección debe tener entre 3 y 63 caracteres.")
    if ".." in name or not _NAME.fullmatch(name):
        raise ValueError("El nombre de la colección no es válido para Chroma.")
    return name


def collection_name(
    scope: CollectionScope,
    model: str,
    dimension: int,
) -> str:
    if dimension <= 0:
        raise ValueError("La dimensión debe ser positiva.")

    if scope.kind == "public":
        name = f"public__{_model_slug(model, 24)}__{dimension}"
    else:
        name = f"case__{scope.case_id}__{_model_slug(model, 19)}__{dimension}"
    return validate_collection_name(name)


# --- Namespace de Qdrant por instancia (004) ---------------------------------
#
# Los nombres de Chroma se conservan arriba hasta el corte de retiro. Las
# funciones siguientes construyen los nombres físicos y alias de Qdrant.

_INSTANCE_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{2,39}$")
_GENERATION = re.compile(r"^\d{8}T\d{12}Z$")


def _model_slug_for_qdrant(model: str) -> str:
    return _model_slug(model, 40)


def validate_qdrant_name(name: str) -> str:
    """Los nombres de Qdrant admiten alfanuméricos, guion y guion bajo."""
    if not 3 <= len(name) <= 255:
        raise ValueError("El nombre de colección Qdrant debe tener entre 3 y 255 caracteres.")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name):
        raise ValueError("El nombre de colección Qdrant no es válido.")
    return name


def new_generation_id() -> str:
    """Identificador de generación UTC ordenable y único."""
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    return now.strftime("%Y%m%dT%H%M%S%fZ")


def instance_collection_name(
    instance_id: str,
    scope: CollectionScope,
    model: str,
    dimension: int,
    generation: str,
) -> str:
    if not _INSTANCE_NAME.fullmatch(instance_id):
        raise ValueError("El identificador de instancia no es válido.")
    if dimension <= 0:
        raise ValueError("La dimensión debe ser positiva.")
    if not _GENERATION.fullmatch(generation):
        raise ValueError("La generación no es válida.")
    slug = _model_slug_for_qdrant(model)
    if scope.kind == "public":
        name = f"secguard__{instance_id}__public__{slug}__{dimension}__g{generation}"
    else:
        name = f"secguard__{instance_id}__case__{scope.case_id}__{slug}__{dimension}__g{generation}"
    return validate_qdrant_name(name)


def instance_alias_name(
    instance_id: str,
    scope: CollectionScope,
    model: str,
    dimension: int,
) -> str:
    if not _INSTANCE_NAME.fullmatch(instance_id):
        raise ValueError("El identificador de instancia no es válido.")
    if dimension <= 0:
        raise ValueError("La dimensión debe ser positiva.")
    slug = _model_slug_for_qdrant(model)
    if scope.kind == "public":
        name = f"secguard__{instance_id}__public__{slug}__{dimension}__active"
    else:
        name = f"secguard__{instance_id}__case__{scope.case_id}__{slug}__{dimension}__active"
    return validate_qdrant_name(name)
