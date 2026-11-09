# AGENTS — SecGuard Advisor

Contexto del proyecto para sesiones con asistentes LLM. Está versionado en el repositorio.

## Proyecto

SecGuard Advisor es un agente consultor defensivo para ciberseguridad empresarial y seguridad de
aplicaciones de IA. Analiza documentación, contexto organizacional y hallazgos técnicos, identifica
brechas y prepara recomendaciones respaldadas por evidencia, con supervisión humana.

**Estado actual**: base técnica, US1–US4 (cortes T001–T074) y la navegación aprobada. La
aplicación arranca con `/healthz`, casos, documentos, consulta documental con citas y revisión humana
del respaldo, con memoria por caso en checkpoints separados. Todavía no hay herramienta de
hallazgos, traza real ni recorrido de aceptación.

La interfaz es multipágina con renderizado del servidor: cabecera, barra lateral persistente en
escritorio, menú desplegable en móvil y una sección visible por ruta. Las secciones son `/cases`,
`/cases/new`, `/cases/{id}` (resumen), `/cases/{id}/documents` y `/cases/{id}/chat`; la evidencia de
ejecución vive en `/cases/{id}/runs/{run_id}`. HTMX se conserva solo dentro de cada sección.

La verdad normativa vive en [`CONSTITUTION.md`](./CONSTITUTION.md), que es un enlace simbólico a
`.specify/memory/constitution.md`. Se edita únicamente el archivo real; nunca se mantienen dos
copias. Ante cualquier cambio arquitectónico, tecnológico o de proceso, actualiza la constitución en
el mismo commit.

## Stack

- Python 3.14.6, `uv`, src-layout, `uv_build`.
- FastAPI, Jinja2, HTMX, Tailwind CSS y Flowbite (gratuito), recursos locales.
- LangChain, LangGraph, Ollama, SQLite, Chroma, LangSmith.
- pytest, Ruff, pre-commit, Makefile y GitHub Actions.

## Estructura

```text
src/secguard_advisor/     código del paquete
tests/                    unit, contract, integration, acceptance, fixtures
docs/                     planificación, referencias y evidencia
specs/001-consulta-documental/  spec, plan, research, data-model, contracts, tasks
.specify/                 Spec Kit y constitución normativa
```

## Comandos

```bash
make help               # lista los objetivos
make install            # uv sync --locked + hooks + npm ci
make assets             # compila Tailwind y copia recursos vendorizados
make lint               # Ruff
make format             # Ruff format
make test               # pruebas rápidas, sin integración
make test-integration   # pruebas reales con Ollama y Chroma
make check              # lint + formato + pruebas
make dev                # servidor con casos, documentos y consulta, un worker
make corpus             # descarga y verifica el corpus oficial
make corpus-ingest      # ingesta el corpus verificado
make seed-demo          # dataset sintético; requiere el esquema migrado
uv run alembic upgrade head  # crea/actualiza el esquema
SECGUARD_REVIEWER_NAME="Nombre" make dev  # habilita la revisión humana declarada
```

`make corpus` y `make corpus-ingest` están implementados y son las vías autorizadas para el corpus.
El target `demo` informa «no implementado» hasta el recorrido de aceptación. `seed-demo` requiere el
esquema migrado. El esquema se crea y evoluciona solo con Alembic; la aplicación no ejecuta
`create_all` al arrancar.

## Reglas duras

- Toda gestión de dependencias pasa por `uv`. Prohibido `pip` y `requirements.txt`.
- `uv.lock` se versiona. `uv sync --locked` debe reproducir el entorno.
- Ruff para lint y formato; pre-commit instalado; `make check` en verde antes de integrar.
- pytest con patrón AAA. Las pruebas de integración usan Ollama y recuperación reales; los mocks
  solo en pruebas unitarias identificadas.
- Documentación e interfaz en español. Código, identificadores, tablas y comentarios en inglés.
- Conventional Commits. Sin atribución de IA.
- No se versionan secretos, `.env`, `storage/` ni `data/corpus/originals/`.
- No se descarga corpus, no se cargan modelos grandes ni se ejecutan APIs pagadas sin una tarea que
  lo autorice. `make corpus` y `make corpus-ingest` son las vías autorizadas para el corpus.
- Los originales del corpus no se versionan; el manifiesto `data/corpus/manifest.json` sí.
- No hay OCR: un PDF escaneado se reporta como «sin texto utilizable».
- Un solo proceso y un worker. El semáforo global de generación y la reconciliación de arranque lo
  asumen.
- No se publica repositorio, no se hace push ni se despliega nada sin autorización explícita.
- No se modifica la configuración global de Git. La identidad local del repositorio ya está
  definida.
- `SECGUARD_REVIEWER_NAME` es una identidad local declarada para la revisión humana; no es
  autenticación. Sin esa variable no se escribe ninguna revisión.
- El historial visible es la fuente autoritativa (`messages`). `storage/checkpoints.sqlite` es
  memoria operativa y se reconcilia antes de cada turno; no hay atomicidad entre bases.
- El historial del prompt se acota a 8 mensajes y 6000 caracteres, y la evidencia a 3500 tokens
  medidos al ingerir. El historial no es evidencia: las citas se validan contra los fragmentos del
  turno actual.
- El umbral de recuperación es un filtro de candidatos débiles; una recuperación vacía no demuestra
  ausencia de evidencia. El generador configurado es `qwen3.5:9b`, con razonamiento desactivado.
- No se declaran resultados, métricas ni estados de CI antes de ejecutarlos.

## Spec Kit

El flujo es: constitución → especificación → aclaraciones → plan → tareas → análisis →
implementación por incrementos. Los artefactos activos están en
`specs/001-consulta-documental/`. No se amplía el alcance sin una decisión explícita.

## Búsqueda de código

Si `tgrep` está instalado, úsalo para búsquedas de código en lugar de `grep` o `find`. En OpenCode
la preferencia se aplica mediante `.opencode/rules/tgrep.md`.
