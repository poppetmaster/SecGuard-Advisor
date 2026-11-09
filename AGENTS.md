# AGENTS — SecGuard Advisor

Contexto del proyecto para sesiones con asistentes LLM. Está versionado en el repositorio.

## Proyecto

SecGuard Advisor es un agente consultor defensivo para ciberseguridad empresarial y seguridad de
aplicaciones de IA. Analiza documentación, contexto organizacional y hallazgos técnicos, identifica
brechas y prepara recomendaciones respaldadas por evidencia, con supervisión humana.

**Estado actual**: base técnica, US1–US6 y T088–T095 (cortes T001–T095). La aplicación arranca con
`/healthz`, casos, documentos, consulta documental con citas y revisión humana del respaldo, memoria
por caso en checkpoints separados, la herramienta `findings_query` acotada al caso y la evidencia de
ejecución con intentos, límites y trazas. La aceptación local está documentada en
`docs/evidencia/demo-001.md`. SC-001 (recorrido humano cronometrado) y SC-003 (diez revisiones
semánticas) son validaciones recomendadas y no bloqueantes; no se ejecutaron y no se presentan como
aprobadas. La revisión en otros navegadores sigue pendiente.

**US1–US3 de 002 implementadas**: el módulo `vulnerabilities` procesa el CSV filtrado de Qualys de
forma local con lector, políticas versionadas, validación por fila, staging/rechazo, snapshots
confirmables, comparación de manifiesto y posibles repeticiones. La sección «Vulnerabilidades» incluye
formulario, vista previa, confirmación, cancelación, historial, selector de instantáneas, filtros por
estado, severidad, prioridad e indicadores, y consulta de registros confirmados mediante
`findings_query` (origen, instantánea, estado, severidad, prioridad e indicadores incluidos). La
primera consulta de un turno fija el snapshot y las posteriores lo reutilizan. El corte final añade
privacidad de payloads, evidencia histórica sobre el snapshot persistido, separación del RAG y
aceptación real local con el CSV filtrado y Ollama. SC-001, SC-003 y la CI remota no se ejecutaron.

La interfaz es multipágina con renderizado del servidor: cabecera, barra lateral persistente en
escritorio, menú desplegable en móvil y una sección visible por ruta. Las secciones son `/cases`,
`/cases/new`, `/cases/{id}` (resumen), `/cases/{id}/documents`, `/cases/{id}/vulnerabilities` y
`/cases/{id}/chat`; la evidencia de ejecución vive en `/cases/{id}/runs/{run_id}`. HTMX se conserva
solo dentro de cada sección.

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
  solo al detalle y un CVE con varias relaciones no multiplica filas. La herramienta consulta por
  defecto la última instantánea Qualys confirmada y distingue origen sintético/importado; los
  resultados importados identifican la instantánea y no se mezclan con las etiquetas sintéticas. La
  primera resolución de importación fija el snapshot del turno y otra solicitud devuelve
  `snapshot_locked`. Solo se consultan importaciones `confirmed`, no se envían `Results` al modelo y
  los registros Qualys no se convierten en documentos, vectores ni citas del RAG. Un total 0 no
  demuestra ausencia de vulnerabilidades ni implica remediación.
- La severidad importada usa la escala del proyecto 1 Informativa, 2 Baja, 3 Media, 4 Alta y 5
  Crítica; conserva el valor original y no se equipara con CVSS, QDS, TruRisk ni prioridades P1–P4.
  Los estados se agrupan en `pending_known` (Active, New, Re-Opened), `fixed` y `manual_review`
  (desconocido); un estado desconocido no es un indicador indeterminado. Explotabilidad y malware son
  distribuciones independientes y la prioridad conjunta solo aplica con ambos positivos; `Fixed` con
  ambos positivos es antecedente, no remediación pendiente.
- La tabla y `findings_query` comparten filtros. `origin=imported` usa `pending_known` por defecto;
  `origin=all` usa `all`, devuelve bloques separados y solo admite `status_group=all`. Los filtros
  importados exigen `origin=imported`. La UI conserva la instantánea seleccionada y los parámetros en
  la URL, muestra filtros activos y distingue «Sin importaciones confirmadas» de «Sin registros para
  estos filtros».
- `manual_review_rows` cuenta una vez los registros con estado desconocido, explotabilidad
  indeterminada o malware indeterminado. Se presenta como «Registros que requieren revisión de estado
  o indicadores»; no se suma con las distribuciones y no convierte un estado Active/New/Re-Opened/
  Fixed en revisión manual.
- La evidencia histórica recalcula el detalle solo sobre el `snapshot_id` del resumen persistido y
  conserva los filtros originales; muestra la instantánea usada y «Consulta actual» sin sustituir el
  resumen. La importación no crea documentos, fragmentos, vectores ni citas del RAG. Las trazas
  externas envían metadatos acotados y nunca pregunta, prompts, documentos, argumentos, resultados de
  fila, claves ni rutas locales; `Results` completo no llega al modelo ni a la interfaz.
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
  significa verificado. `confirmed` lo escribe únicamente `scripts/confirm_trace.py` tras verificar
  por API de lectura que la traza existe, pertenece al proyecto y coincide con `run_id`, `case_id` e
  intento, registrando identidad declarada, fecha y evidencia. Las trazas envían metadatos acotados:
  nunca pregunta, prompts, documentos del caso, argumentos de herramienta, claves ni rutas locales.
- Las pruebas de aceptación con dobles viven en `tests/acceptance/test_journey.py`; la aceptación real
  con Ollama, corpus y herramienta en `tests/acceptance/test_journey_real.py`, siempre con
  almacenamiento separado (`SECGUARD_ACCEPTANCE_DIR` o `tmp_path`). `make demo-prepare` prepara
  `storage/demo` con migraciones, corpus y seed; `make demo` arranca esa misma instancia. No modifica
  `storage/`.
- No se declaran resultados, métricas ni estados de CI antes de ejecutarlos.

## Spec Kit

El flujo es: constitución → especificación → aclaraciones → plan → tareas → análisis →
implementación por incrementos. Los artefactos activos están en
`specs/001-consulta-documental/`. No se amplía el alcance sin una decisión explícita.

## Búsqueda de código

Si `tgrep` está instalado, úsalo para búsquedas de código en lugar de `grep` o `find`. En OpenCode
la preferencia se aplica mediante `.opencode/rules/tgrep.md`.
