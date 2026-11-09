"""Contexto de navegación compartido por las páginas."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Crumb:
    """Elemento de la ruta de navegación; sin ``href`` es el elemento actual."""

    label: str
    href: str | None = None


def page(
    *,
    title: str,
    section: str | None,
    case_id: str | None = None,
    case_title: str | None = None,
    crumbs: tuple[Crumb, ...] = (),
) -> dict:
    """Devuelve el contexto que consume la plantilla base."""
    nav_case = None
    if case_id and case_title:
        nav_case = {"id": case_id, "title": case_title}
    return {
        "page_title": title,
        "active_section": section,
        "nav_case": nav_case,
        "breadcrumbs": crumbs,
    }


def case_crumbs(case_id: str, case_title: str, *trail: Crumb) -> tuple[Crumb, ...]:
    """Ruta de navegación de un caso: Casos / nombre / sección."""
    base = (
        Crumb("Casos", "/cases"),
        Crumb(case_title, f"/cases/{case_id}"),
    )
    return base + trail
