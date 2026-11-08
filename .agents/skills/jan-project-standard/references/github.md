# Gobernanza de GitHub

Cómo se crea, conecta, protege y presenta un repositorio del estándar.

## Creación y conexión

La cuenta es **tu usuario de GitHub** (`<tu-usuario>`) y la autenticación preferida es **SSH** con
`~/.ssh/id_ed25519` (la identidad se resuelve sola dentro de
`~/Desktop/Repositorios/personal/`; ver `references/agent-context.md`).

```bash
# Opción 1 — repo nuevo, ya conectado y con push inicial
gh repo create <tu-usuario>/<repo> --private --source=. --remote=origin --push

# Opción 2 — el repo ya existe en GitHub
git init
git branch -M main
git remote add origin git@github.com:<tu-usuario>/<repo>.git
git add -A
git commit -m "chore: bootstrap del proyecto"
git push -u origin main
```

> **Gotcha:** el *credential helper* de `gh` puede estar asociado a otra cuenta. Si las
> operaciones por HTTPS fallan con `Repository not found`, usa **SSH**.
>
> **Gotcha (repo existente no vacío):** `gh repo create --push` falla si el repo remoto
> ya tiene contenido. En ese caso, clona, mueve el contenido o haz `git pull --rebase`.

## Protección de `main`

Activa, como mínimo:

- Requerir Pull Request antes de fusionar.
- Requerir que la CI (`CI / Calidad`) pase.
- Requerir la rama actualizada respecto a `main`.
- Prohibir el push directo (cuando el tamaño del equipo lo justifique).

```bash
# Ejemplo (requiere permisos de admin)
gh api -X PUT repos/<tu-usuario>/<repo>/branches/main/protection \
  -F required_status_checks.strict=true \
  -F 'required_status_checks.contexts[]=Calidad' \
  -F enforce_admins=true \
  -F required_pull_request_reviews.required_approving_review_count=1
```

Datos recomendados del repositorio: descripción, *topics*, y
`delete_branch_on_merge = true`.

## README profesional

Estructura recomendada (ver `assets/templates/base/README.md`):

1. **Encabezado centrado** (`<div align="center">`) con título, subtítulo y badges.
2. **Descripción general** (qué es y para qué sirve).
3. **Estado del proyecto** (tabla ✅/🚧/⏳).
4. **Información académica** (solo proyectos de curso/TG).
5. **Stack tecnológico** (tabla).
6. **Primeros pasos** (requisitos + instalación con `uv`).
7. **Calidad y automatización** (herramientas + comandos `make`).
8. **Estructura del repositorio** (árbol `text`).
9. **Flujo de trabajo y contribución** (enlace a `CONTRIBUTING.md`).
10. **Documentación** (tabla de enlaces, incluyendo `CONSTITUTION.md`).
11. **Autores** y **Licencia**.

### Badges usuales

```markdown
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/<tu-usuario>/<repo>/actions/workflows/ci.yml/badge.svg)](https://github.com/<tu-usuario>/<repo>/actions/workflows/ci.yml)
[![Managed with uv](https://img.shields.io/badge/managed%20with-uv-de5fe9.svg)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=precommit&logoColor=white)](./.pre-commit-config.yaml)
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-fe5196.svg)](https://conventionalcommits.org)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](./CONTRIBUTING.md)
[![skills.sh](https://skills.sh/b/<tu-usuario>/<repo>)](https://skills.sh/<tu-usuario>/<repo>)
```

> Usa **endpoint badges** (Ruff) o **badges dinámicos** (última acción, último commit)
> solo cuando el dato exista; un badge roto es peor que ninguno.

## Plantilla de Pull Request

`.github/pull_request_template.md` debe exigir, como mínimo:

- Título con prefijo de Conventional Commits (tabla de prefijos).
- Tipo de cambio (código / investigación / documentación).
- Descripción con trazabilidad (issue/Kanban).
- Cómo se probó (comandos + tabla de casos).
- Checklist pre-PR: pruebas, lint, `uv.lock`, sin secretos, `CONSTITUTION.md` actualizado,
  PR acotado.
- Integración y post-merge (squash, cerrar issue, borrar rama, actualizar tablero).

Modelo completo en `assets/templates/github/pull_request_template.md`.

## Plantillas de issues

Tres formularios YAML en `.github/ISSUE_TEMPLATE/`:

| Plantilla | Etiqueta | Uso |
|-----------|----------|-----|
| `bug_report.yml` | `bug` | Fallos reproducibles. |
| `feature_request.yml` | `enhancement` | Nuevas funcionalidades con criterios de aceptación. |
| `spike.yml` | `spike` | Investigación acotada (pregunta + timebox + entregable). |

`config.yml` desactiva los issues en blanco y enlaza a la constitución, la guía de
contribución y el código de conducta.

> **Gotcha:** una etiqueta que no exista en el repo **no se aplica** (no rompe el
> formulario, pero el issue queda sin etiqueta). Asegúralas con `labels.yml`.

## CI (GitHub Actions)

`.github/workflows/ci.yml`: `checkout` → `astral-sh/setup-uv` (con caché por `uv.lock`)
→ `uv sync --all-groups` → `pre-commit run --all-files` → `pytest`. Si aplica:
`ty check`.

Patrón observado (Astral recomienda el flujo oficial); *pinea* versiones de Actions y
usa `concurrency` para cancelar ejecuciones viejas.

```yaml
- uses: astral-sh/setup-uv@v10.2.0
  with:
    enable-cache: true
    cache-dependency-glob: uv.lock
```

> **Gotcha:** `setup-uv` no siempre publica tag flotante para la major; fija la versión
> exacta (p. ej. `@v10.2.0`) para que el workflow sea reproducible.

## Dependabot

`.github/dependabot.yml` para `uv` y `github-actions` (semanal, lunes, límite de PRs,
labels `chore`/`infra` y prefijo `chore`). Ver plantilla.

## Labels declarativas

`.github/labels.yml` es la **fuente única** de etiquetas. El workflow
`labels.yml` las sincroniza con `crazy-max/ghaction-github-labeler` (`skip-delete: true`
para no borrar sorpresas). Agrupa por **tipo** (`bug`, `enhancement`, `documentation`,
`spike`, `refactor`, `test`, `chore`) y por **área** (dominio del proyecto).

> Los formularios usan `bug` y `enhancement` (existen por defecto). `spike` debe existir:
> créala con `gh label create spike` o vía `labels.yml`.

## Estrategia de ramas y commits

- `main` es la rama estable; se integra por **Pull Request**.
- Ramas: `feat/...`, `fix/...`, `docs/...`, `refactor/...`, `test/...`, `chore/...`.
- Commits: [Conventional Commits](https://www.conventionalcommits.org/).
- Integración con **Squash & Merge** (salvo indicación), y se elimina la rama.

> **Regla de oro:** nunca `git push` a `main` "para ver si la CI pasa". Verifica local
> con `make check` antes.
