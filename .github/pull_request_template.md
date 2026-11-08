<!--
Gracias por contribuir a SecGuard Advisor.
Completa todas las secciones aplicables. Un PR con contexto insuficiente no será revisado.

Antes de abrir este PR, verifica que leíste CONSTITUTION.md.
-->

## Convención del título

Usa un prefijo de [Conventional Commits](https://www.conventionalcommits.org/) en el título:

| Prefijo | Cuándo usarlo |
|---|---|
| `feat:` | Funcionalidad nueva |
| `fix:` | Corrección de bug |
| `docs:` | Documentación |
| `refactor:` | Refactorización sin cambio de comportamiento |
| `test:` | Pruebas |
| `chore:` | Mantenimiento o configuración |

## Tipo de cambio

- [ ] **Código / Producto** — afecta la aplicación. Requiere `make check` en verde.
- [ ] **Investigación / Exploración** — prototipos o experimentos. Documenta hallazgos.
- [ ] **Documentación / Gestión** — README, constitución, especificación o material académico.

## Descripción

<!-- Qué logra este cambio y por qué. -->

**Resuelve:** <!-- Closes #N -->

**Trazabilidad:** <!-- Issue, tarea o tarjeta relacionada -->

## Checklist

- [ ] `make check` termina satisfactoriamente.
- [ ] Se añadieron o actualizaron las pruebas correspondientes.
- [ ] `uv.lock` está sincronizado.
- [ ] `CONSTITUTION.md` se actualizó si cambió arquitectura, tecnología o proceso.
- [ ] La documentación afectada se actualizó en el mismo commit.
- [ ] No se añadieron secretos, `.env`, datos locales ni originales del corpus.
- [ ] El cambio está acotado a un solo propósito.

## Evidencia

<!-- Salidas de comandos, capturas, trazas o resultados observados. -->
