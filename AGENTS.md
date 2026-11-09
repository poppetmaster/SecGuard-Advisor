# AGENTS — SecGuard Advisor

Contexto del proyecto para sesiones con asistentes LLM. Está versionado en el repositorio.

## Proyecto

SecGuard Advisor es un agente consultor defensivo para ciberseguridad empresarial y seguridad de
aplicaciones de IA. Analiza documentación, contexto organizacional y hallazgos técnicos, identifica
brechas y prepara recomendaciones respaldadas por evidencia, con supervisión humana.

**Estado actual**: base técnica, US1–US6 (cortes T001–T087) y la navegación aprobada. La aplicación
arranca con `/healthz`, casos, documentos, consulta documental con citas y revisión humana del
respaldo, memoria por caso en checkpoints separados, la herramienta `findings_query` acotada al caso
y la evidencia de ejecución con intentos, límites y trazas. La aceptación real, la confirmación de la
traza (T091) y el paquete de evidencia (T088–T095) siguen pendientes.

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
- El historial del prompt se acota a 8 mensajes y 6000 caracteres. El historial no es evidencia:
  las citas se validan contra los fragmentos del turno actual.
- Antes de cada generación se mide el prompt con el tokenizador del modelo (vocabulario y BPE del
  GGUF instalado) y su plantilla, no con el `token_count` de EmbeddingGemma ni con un divisor por
  bytes. Si no cabe, se reduce historial y luego fuentes; si el mínimo no cabe,
  `context_budget_exceeded`; si falta el tokenizador, `context_budget_unavailable` (503).
- El umbral de recuperación es un filtro de candidatos débiles; una recuperación vacía no demuestra
  ausencia de evidencia. El generador configurado es `qwen3.5:9b`, con razonamiento desactivado.
- `findings_query` recibe el alcance por clausura: `case_id` no es argumento ni aparece en el resultado
  expuesto al modelo. Los conteos se calculan en SQLite sobre los filtros aplicados; el límite afecta
  solo al detalle y un CVE con varias relaciones no multiplica filas. El resultado se presenta como
  «Datos educativos sintéticos», nunca como una importación de Qualys; un total 0 no demuestra
  ausencia de vulnerabilidades.
- La selección de herramienta usa una llamada estructurada `ToolDecision` antes de la respuesta:
  Ollama no emite `tool_calls` nativos junto con `format`. Son como máximo dos ejecuciones por turno y
  la decisión también se mide con el tokenizador del generador.
- Los límites del turno son: 8 operaciones de modelo o herramienta, 2 llamadas a herramientas, 1
  reparación, 120 s de turno y 90 s por llamada al modelo. La decisión de herramienta consume paso y
  tiempo; ninguna llamada recibe un presupuesto nuevo después de otra.
- La página «Ver ejecución» lee solo registros persistidos. Si recalcula el detalle de una herramienta,
  lo rotula como consulta actual; los totales y grupos son históricos. El control automático de citas
  y la revisión humana se muestran por separado.
- `trace_status` solo puede ser `disabled`, `submitted` o `failed` por la aplicación; `submitted` no
  significa verificado. `confirmed` lo escribe únicamente `scripts/confirm_trace.py` en la aceptación.
  Las trazas envían metadatos acotados: nunca pregunta, prompts, documentos del caso, argumentos de
  herramienta, claves ni rutas locales.
- No se declaran resultados, métricas ni estados de CI antes de ejecutarlos.

## Spec Kit

El flujo es: constitución → especificación → aclaraciones → plan → tareas → análisis →
implementación por incrementos. Los artefactos activos están en
`specs/001-consulta-documental/`. No se amplía el alcance sin una decisión explícita.

## Búsqueda de código

Si `tgrep` está instalado, úsalo para búsquedas de código en lugar de `grep` o `find`. En OpenCode
la preferencia se aplica mediante `.opencode/rules/tgrep.md`.
