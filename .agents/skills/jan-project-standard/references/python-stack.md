# Stack Python — `uv` + Astral + calidad automatizada

Este documento detalla la capa Python del estándar: entorno, dependencias, linting,
formato, tipado, pruebas, hooks y Makefile.

## Regla dura de entorno

- **Todo** pasa por [`uv`](https://docs.astral.sh/uv/): crear entorno, instalar,
  ejecutar, bloquear, construir.
- **Prohibido:** `pip install`, `requirements.txt`, entornos manuales con `venv`.
- Dependencias declaradas en `pyproject.toml`; **`uv.lock` se versiona**.
- Entorno virtual en `.venv/` (ignorado por Git).
- Versión de Python fijada en `.python-version` (`3.13`).

Comandos base:

```bash
uv sync                    # crea/actualiza el entorno desde pyproject + uv.lock
uv add <paquete>           # añade una dependencia de producción
uv add --dev <paquete>     # añade una dependencia de desarrollo
uv run <comando>           # ejecuta dentro del entorno (sin activar nada)
uv lock                    # regenera el lockfile
uv build                   # construye sdist + wheel
```

## `pyproject.toml` canónico

```toml
[project]
name = "mi-proyecto"
version = "0.1.0"
description = "Descripción breve."
readme = "README.md"
license = "MIT"
license-files = ["LICENSE"]
requires-python = ">=3.13"
authors = [{ name = "<Tu Nombre>", email = "<tu-correo>" }]
classifiers = [
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.13",
    "Typing :: Typed",
]
dependencies = []

[project.urls]
Homepage = "https://github.com/<tu-usuario>/mi-proyecto"
Repository = "https://github.com/<tu-usuario>/mi-proyecto"
Issues = "https://github.com/<tu-usuario>/mi-proyecto/issues"

[build-system]
requires = ["uv_build>=0.12.2,<0.13.0"]
build-backend = "uv_build"

[dependency-groups]
dev = [
    "pre-commit>=3.7",
    "pytest>=8.0",
    "ruff>=0.6",
    "ty>=0.0.1",
]

[tool.ruff]
line-length = 100
target-version = "py313"
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM", "RUF", "C4"]

[tool.ruff.lint.isort]
known-first-party = ["mi_proyecto"]

[tool.ruff.format]
quote-style = "double"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
```

> Ajusta la versión de `uv_build` a la de `uv` instalada (`uv --version`). El scaffolder
> la fija a `0.12.2` por defecto.
>
> Excepción de `target-version`: si un hook `ruff-pre-commit` antiguo falla con
> `unknown variant`, baja a `py312` (sintaxis TOML válida ≠ schema válida del hook).

## Ruff

- **Lint + formato** en una sola herramienta (reemplaza flake8/isort/black).
- Reglas base: `E` (pycodestyle), `F` (pyflakes), `I` (isort), `B` (bugbear),
  `UP` (pyupgrade), `SIM` (simplify), `RUF`, `C4` (comprehensions).
- `line-length = 100`, comillas dobles, `src = ["src", "tests"]`.

```bash
uv run ruff check .          # lint
uv run ruff check --fix .    # lint con autocorrección
uv run ruff format .         # formato
uv run ruff format --check . # verificar sin modificar
```

## Tipado estático con `ty` (opcional)

El estándar recomendado (ecosistema Astral) incluye [`ty`](https://github.com/astral-sh/ty).

- Marca el paquete como tipado con `src/<paquete>/py.typed` (PEP 561) y el clasificador
  `Typing :: Typed`.
- Añade anotaciones en funciones y firmas públicas.
- `uv run ty check` en el Makefile y en el CI.

Si un proyecto no lo usa, genera con `--no-types` (omite `ty` de dependencias, Makefile,
CI y docs).

## Pruebas con pytest

- Viven en `tests/`, nombradas `test_*.py`.
- Patrón **AAA** (Arrange · Act · Assert), una responsabilidad por test.
- Sin dependencias externas reales: usa *fixtures*, dobles o datos sintéticos.
- Nunca subas datos personales reales a fixtures.

```python
def test_promedio_de_lista_vacia_es_cero() -> None:
    # Arrange
    valores: list[int] = []

    # Act
    resultado = promedio(valores)

    # Assert
    assert resultado == 0
```

## `.pre-commit-config.yaml` canónico

```yaml
default_language_version:
  python: python3.13

minimum_pre_commit_version: "3.7.0"
fail_fast: false

repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: check-added-large-files
        args: ["--maxkb=2048"]
      - id: check-case-conflict
      - id: check-merge-conflict
      - id: check-json
      - id: check-toml
      - id: check-yaml
        args: ["--allow-multiple-documents"]
      - id: end-of-file-fixer
      - id: trailing-whitespace
        args: ["--markdown-linebreak-ext=md"]
      - id: mixed-line-ending
      - id: detect-private-key

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.16.9
    hooks:
      - id: ruff
        args: ["--fix", "--exit-non-zero-on-fix"]
      - id: ruff-format

  - repo: https://github.com/astral-sh/uv-pre-commit
    rev: 0.12.2
    hooks:
      - id: uv-lock
```

Instalación y uso:

```bash
uv run pre-commit install              # una vez por clon
uv run pre-commit run --all-files      # sobre todo el repo
```

## Makefile — interfaz del proyecto

Contrato mínimo de targets (todos documentados con `## ` para `make help`):

| Target | Acción |
|--------|--------|
| `help` | Lista los targets (objetivo por defecto). |
| `install` | `uv sync`. |
| `dev` | `install` + `uv run pre-commit install`. |
| `lint` | `uv run ruff check .` |
| `format` | `uv run ruff format .` |
| `format-check` | `uv run ruff format --check .` |
| `typecheck` | `uv run ty check` (si aplica). |
| `test` | `uv run pytest`. |
| `check` | lint + format-check + (typecheck) + test. |
| `pre-commit` | `uv run pre-commit run --all-files`. |
| `build` | `uv build`. |
| `clean` | Limpia cachés y artefactos. |

Usa `SHELL := /bin/bash`, `.DEFAULT_GOAL := help` y `.PHONY`. Las tabulaciones son
reales en las recetas (no espacios).

## `.editorconfig`

```ini
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true
indent_style = space
indent_size = 4

[*.{yml,yaml,json,toml}]
indent_size = 2

[*.{md,markdown}]
trim_trailing_whitespace = false

[Makefile]
indent_style = tab
```

## `.gitignore`

Ignora al menos: `__pycache__/`, `*.py[oc]`, `build/`, `dist/`, `*.egg-info/`,
`.venv/`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `.coverage`, `htmlcov/`,
`.env`, `.env.*` (con `!.env.example`), artefactos pesados (`*.h5`, `*.pt`, `*.onnx`,
`*.safetensors`, `*.sqlite`, `*.db`), datos crudos y residuales del sistema/IDE.

## Errores comunes

| Síntoma | Causa / solución |
|---------|------------------|
| `ruff-pre-commit` falla con `unknown variant` en `target-version` | Hook antiguo no conoce `py313`; usa `py312` o sube el hook. |
| `uv-lock` hook falla | `uv.lock` desincronizado; ejecuta `uv lock`. |
| pnpm/pip no instala binarios | pnpm 10 requiere `onlyBuiltDependencies`; para Python la regla es no usar pip. |
| `unknown command` al correr `ty` | `ty` no está en dev deps; añádelo con `uv add --dev ty` o usa `--no-types`. |
