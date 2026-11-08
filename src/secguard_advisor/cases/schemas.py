"""Entradas validadas para la gestión de casos."""

from dataclasses import dataclass

MAX_TITLE = 200
MAX_ASSET_NAME = 120


class CaseValidationError(ValueError):
    """Errores de validación asociados a campos del formulario."""

    def __init__(self, errors: dict[str, str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors.values()))


def _optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


@dataclass(frozen=True, slots=True)
class CaseInput:
    """Datos validados para crear un caso."""

    title: str
    description: str | None
    ai_application: str | None
    data_processed: str | None
    restrictions: str | None
    assets: tuple[str, ...]

    @classmethod
    def from_form(
        cls,
        *,
        title: str | None,
        description: str | None = None,
        ai_application: str | None = None,
        data_processed: str | None = None,
        restrictions: str | None = None,
        assets: str | None = None,
    ) -> CaseInput:
        """Valida y normaliza los valores del formulario."""
        errors: dict[str, str] = {}

        clean_title = (title or "").strip()
        if not clean_title:
            errors["title"] = "El título es obligatorio."
        elif len(clean_title) > MAX_TITLE:
            errors["title"] = f"El título no puede superar los {MAX_TITLE} caracteres."

        names: list[str] = []
        seen: set[str] = set()
        for line in (assets or "").splitlines():
            name = line.strip()
            if not name:
                continue
            if len(name) > MAX_ASSET_NAME:
                errors["assets"] = f"Cada activo no puede superar los {MAX_ASSET_NAME} caracteres."
                break
            if name not in seen:
                seen.add(name)
                names.append(name)

        if errors:
            raise CaseValidationError(errors)

        return cls(
            title=clean_title,
            description=_optional(description),
            ai_application=_optional(ai_application),
            data_processed=_optional(data_processed),
            restrictions=_optional(restrictions),
            assets=tuple(names),
        )
