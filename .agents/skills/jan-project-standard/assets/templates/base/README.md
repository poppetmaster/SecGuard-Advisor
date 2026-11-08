<div align="center">

# {{PROJECT_NAME}}

**{{DESCRIPTION}}**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python {{PYTHON_VERSION}}+](https://img.shields.io/badge/python-{{PYTHON_VERSION}}%2B-blue.svg)](https://www.python.org/downloads/)
{{#if GITHUB}}[![CI]({{REPO_URL}}/actions/workflows/ci.yml/badge.svg)]({{REPO_URL}}/actions/workflows/ci.yml)
{{/if}}[![Managed with uv](https://img.shields.io/badge/managed%20with-uv-de5fe9.svg)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=precommit&logoColor=white)](./.pre-commit-config.yaml)
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-fe5196.svg)](https://conventionalcommits.org)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](./CONTRIBUTING.md)

</div>

---

## 📖 Descripción general

<!-- Explica qué es el proyecto y para qué sirve. Una o dos secciones breves. -->

> 📘 La verdad técnica central —stack, decisiones, convenciones y flujo— vive en
> [`CONSTITUTION.md`](./CONSTITUTION.md). Es de lectura obligatoria antes de contribuir.

## 📑 Tabla de contenidos

- [Descripción general](#-descripción-general)
- [Estado del proyecto](#-estado-del-proyecto)
- [Stack tecnológico](#-stack-tecnológico)
- [Primeros pasos](#-primeros-pasos)
- [Calidad y automatización](#-calidad-y-automatización)
{{#if ARCHIFY}}- [Arquitectura del proyecto](#-arquitectura-del-proyecto)
{{/if}}- [Estructura del repositorio](#-estructura-del-repositorio)
- [Flujo de trabajo y contribución](#-flujo-de-trabajo-y-contribución)
- [Licencia](#-licencia)

## 🚧 Estado del proyecto

| Área | Estado |
|------|:------:|
| Estructura del repositorio y entorno (`uv`) | ✅ |
| Constitución técnica y gobernanza | ✅ |
| Primera funcionalidad | ⏳ |
| Suite de pruebas | ⏳ |

## 🛠️ Stack tecnológico

| Categoría | Tecnología |
|-----------|------------|
| **Lenguaje** | Python {{PYTHON_VERSION}}+ |
| **Gestor de paquetes** | [`uv`](https://docs.astral.sh/uv/) |
{{#if PACKAGE}}| **Build backend** | `uv_build` (src-layout) |
{{/if}}{{#if TYPES}}| **Tipado estático** | [`ty`](https://github.com/astral-sh/ty) |
{{/if}}| **Testing** | [`pytest`](https://docs.pytest.org/) |
| **Linting / Formato** | [Ruff](https://docs.astral.sh/ruff/) |
| **Pre-commit** | [pre-commit](https://pre-commit.com) |
{{#if GITHUB}}| **CI/CD** | [GitHub Actions](.github/workflows/ci.yml) |
{{/if}}
## 🚀 Primeros pasos

### Requisitos previos

- [Python {{PYTHON_VERSION}}+](https://www.python.org/downloads/)
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- [Git](https://git-scm.com/)

### Instalación

```bash
git clone {{SSH_URL}}
cd {{PROJECT_SLUG}}

uv sync
uv run pre-commit install   # equivalente a: make dev
```

### Verificación

```bash
make check   # lint + formato{{#if TYPES}} + tipos{{/if}} + pruebas
```

> ⚠️ **Regla del proyecto:** toda gestión de dependencias y entornos pasa por `uv`.
> Está **prohibido** `pip` y `requirements.txt`.

## ✅ Calidad y automatización

| Herramienta | Rol |
|-------------|-----|
| [`uv`](https://docs.astral.sh/uv/) | Entornos, dependencias y lockfile determinista. |
| [Ruff](https://docs.astral.sh/ruff/) | Lint y formato. |
{{#if TYPES}}| [`ty`](https://github.com/astral-sh/ty) | Verificación estática de tipos. |
{{/if}}| [pre-commit](https://pre-commit.com) | Hooks antes de cada commit. |
| [pytest](https://docs.pytest.org/) | Pruebas unitarias. |

| Comando | Descripción |
|---------|-------------|
| `make help` | Lista los objetivos disponibles. |
| `make dev` | `uv sync` + instala los hooks de pre-commit. |
| `make check` | Verificación completa (lint + formato{{#if TYPES}} + tipos{{/if}} + pruebas). |
| `make lint` / `make format` | Ruff. |
| `make test` | `pytest`. |
{{#if PACKAGE}}| `make build` | Construye el paquete (sdist + wheel). |
{{/if}}
{{#if ARCHIFY}}## 🗺️ Arquitectura del proyecto

Mapa de arquitectura interactivo (autocontenido, generado con [Archify](https://github.com/tt-a1i/archify)).
Ábrelo en el navegador: `docs/arquitectura.html`.

<!-- Reemplaza esta línea cuando generes el diagrama real:
[![Arquitectura del proyecto (tema oscuro)](docs/arquitectura.visual-check.2048x1320.dark.png)](docs/arquitectura.html)
-->

> Genera/actualiza con: `npx skills add tt-a1i/archify -g` y luego
> `node bin/archify.mjs deliver architecture docs/arquitectura.json docs/arquitectura.html --quality showcase`.
> El JSON es la fuente versionada; el HTML no se edita a mano.

## 📂 Estructura del repositorio

```text
{{PROJECT_SLUG}}/
{{#if PACKAGE}}├── src/{{PACKAGE_NAME}}/        # código del paquete
{{/if}}{{#unless PACKAGE}}├── main.py                  # punto de entrada
{{/unless}}├── tests/                   # pruebas
├── docs/                    # documentación
├── CONSTITUTION.md          # verdad central del proyecto
├── README.md                # este archivo
├── CONTRIBUTING.md          # guía de contribución
├── Makefile                 # automatización de tareas
├── pyproject.toml           # metadatos y dependencias (uv)
└── uv.lock                  # lockfile determinista
```

## 🤝 Flujo de trabajo y contribución

> 📘 La guía completa está en [`CONTRIBUTING.md`](./CONTRIBUTING.md). Resumen:

1. Crea una rama: `git checkout -b feat/nombre-corto`.
2. Desarrolla y verifica: `make check`.
3. Commitea con [Conventional Commits](https://www.conventionalcommits.org/): `git commit -m "feat: ..."`.
4. Abre un Pull Request con la plantilla oficial.
5. Mantén `CONSTITUTION.md` actualizado ante cambios arquitectónicos o tecnológicos.

## 📄 Licencia

Distribuido bajo la [Licencia MIT](./LICENSE).

---

<div align="center">
<sub>Hecho con ❤️ por {{AUTHOR}}</sub>
</div>
