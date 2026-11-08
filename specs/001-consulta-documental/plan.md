# Implementation Plan: Consulta documental con evidencias, memoria por caso y hallazgos

**Branch**: `001-consulta-documental` (sin rama creada; el hook de git no está instalado y el repositorio aún no tiene commits) | **Date**: 2026-11-08 | **Spec**: `specs/001-consulta-documental/spec.md`

**Input**: Especificación funcional 001, constitución v1.0.1 y documentos de `docs/planificacion/`.

## Summary

Monolito modular en un solo proceso. FastAPI sirve páginas Jinja2 con HTMX; el dominio vive en
módulos separados bajo `src/secguard_advisor`. SQLite conserva casos, documentos, versiones,
fragmentos, conversación, hallazgos y ejecuciones. Chroma mantiene un índice vectorial
reconstruible, con una colección por caso y otra para el corpus público. LangChain aporta el
procesamiento documental y la interfaz de embeddings; LangGraph orquesta el turno de
conversación con memoria persistente en una base separada. Ollama ejecuta la inferencia local:
Qwen3.5 9B como generador y EmbeddingGemma como modelo de embeddings. LangSmith recibe trazas
reales cuando está configurado y nunca bloquea la consulta.

El incremento entrega un recorrido completo: caso con contexto sintético → documentos con
procedencia → respuesta citada → seguimiento con memoria → consulta de hallazgos por
herramienta → abstención → reinicio → aislamiento entre casos → evidencia de ejecución.

## Technical Context

**Language/Version**: Python 3.14.6 (fijado por la constitución)

**Primary Dependencies**: FastAPI, Jinja2, HTMX, Tailwind CSS + Flowbite (gratuito), LangChain,
LangGraph, `langgraph-checkpoint-sqlite`, LangSmith, SQLAlchemy, Alembic, pypdf, Chroma,
`langchain-ollama`, pydantic-settings. Node.js solo como herramienta de construcción de CSS/JS,
nunca en tiempo de ejecución.

**Storage**: SQLite (estado y procedencia, `storage/secguard.sqlite3`), SQLite separado para
checkpoints de LangGraph (`storage/checkpoints.sqlite`), Chroma persistente
(`storage/chroma/`), originales content-addressed (`storage/originals/`), corpus público en
`data/corpus/originals/` con manifiesto versionado.

**Testing**: pytest con tres niveles: unitario rápido con simulaciones para CI, contrato de
rutas y herramientas, e integración real con Ollama, embeddings, recuperación y herramienta.

**Target Platform**: máquina local de un solo usuario (macOS/Linux), navegador moderno, sin
servicios externos obligatorios.

**Project Type**: aplicación web monolítica modular.

**Performance Goals**: recuperación en menos de 1 s con el corpus del incremento; turno de
conversación completo en menos de 60 s con Qwen3.5 9B; ingesta de un PDF de 100 páginas en
menos de 60 s. Son metas de diseño, no resultados medidos.

**Constraints**: sin CDN; sin streaming; un solo generador grande cargado a la vez; **un solo
proceso de aplicación y un worker**; **un semáforo global de una generación**; contexto de
generación fijado explícitamente; 2048 tokens de entrada para embeddings; carga máxima de archivo
configurable (20 MB por defecto); operación sin autenticación pero con alcance por caso impuesto en
el servidor.

**Scale/Scope**: un usuario, decenas de casos, corpus de cinco documentos y unos cientos de
páginas, hallazgos sintéticos de dos centenares de filas. Sin multiempresa ni concurrencia
significativa.

## Constitution Check

*GATE: verificado antes de la Fase 0 y re-evaluado tras el diseño de la Fase 1.*

| Principio | Cómo lo cumple el diseño | Estado |
|---|---|---|
| I. Propósito y alcance | Solo recomendaciones y borradores; sin remediaciones ni certificación | PASS |
| II. Construcción reproducible | uv, src-layout, uv_build, Ruff, pre-commit, pytest, Makefile, CI con paridad | PASS |
| III. Arquitectura modular | Módulos separados; SQLite fuente de verdad; Chroma derivado; recursos locales | PASS |
| IV. Ejecución local | Ollama, un generador a la vez, modelos y versiones registrados por ejecución | PASS |
| V. Recuperación verificable | Originales, manifiesto con SHA-256, citas localizables, límite de embeddings comprobado | PASS |
| VI. Separación de datos | Corpus público, evidencia de caso y evaluación en espacios físicos distintos | PASS |
| VII. Seguridad | `CaseScope` en el servidor, colecciones por caso, herramienta con alcance en clausura | PASS |
| VIII. Evidencia e incertidumbre | Citas validadas por código; abstención cuando no hay cita ni resultado de herramienta; conteos por SQL | PASS |
| IX. Revisión humana | Fuera del incremento; toda respuesta se marca como borrador | PASS |
| X. Evaluación independiente | Conjunto final reservado y aislado; no se usa para ajustar | PASS |
| XI. Observabilidad y costos | LangSmith opcional y no bloqueante; evidencia local mínima; sin proveedor pagado | PASS |
| XII. Desarrollo incremental | Cortes por historia con pruebas y CI desde el primer corte | PASS |

Sin violaciones que requieran justificación. Las dos decisiones que rozan el límite se
registran en Complexity Tracking por transparencia, no por incumplimiento.

**Re-evaluación tras la Fase 1**: sin cambios. El modelo de datos, los contratos y la guía de
validación no introducen acceso fuera del alcance, ni mezcla de espacios, ni evaluación con el
conjunto reservado.

### Correcciones aplicadas a la especificación

Se detectaron dos contradicciones y **ya fueron aplicadas en `spec.md`** el 2026-11-08, con el
checklist actualizado. Se documentan aquí porque cambian el diseño y las tareas.

1. **FR-020 se limitó a evidencias privadas.** El requisito original decía que todo documento
   pertenecía a un único caso, lo que excluía al corpus público.
   *Redacción vigente*: «Todo documento de origen *evidencia del caso* DEBE pertenecer a un único
   caso. Las fuentes públicas de referencia pertenecen al corpus compartido, no a un caso, y son
   accesibles desde cualquier caso.»
   *Efecto*: acceso (las fuentes públicas se leen sin alcance de caso), recuperación (colección
   pública separada de las colecciones de caso) y citas (la cita pública no lleva `case_id` pero se
   valida contra la colección y el documento públicos).

2. **SC-003 se separó en dos controles.** El criterio original no era automatizable.
   *Redacción vigente*: revisión humana de 10 afirmaciones; la compuerta automática solo prueba
   existencia, localización y coincidencia literal. Se añadieron FR-065 y FR-066 para registrar la
   revisión semántica y para impedir que una cita válida se presente como fundamentación probada.

3. **Corrección de diseño detectada al derivar tareas.** La abstención determinista por
   «recuperación vacía» habría bloqueado las preguntas de hallazgos, que no tienen candidatos
   documentales. *Corrección aplicada*: con recuperación vacía el agente **sí** se ejecuta con la
   herramienta disponible; la abstención se decide después, cuando no hay ni citas válidas ni
   resultado de herramienta. El umbral de recuperación filtra candidatos débiles; no decide por sí
   solo que no exista evidencia.

### Segunda ronda: revisión de consistencia (2026-11-08)

Se aplicaron las correcciones del análisis previo. Ninguna cambia el alcance.

| Hallazgo | Resolución |
|---|---|
| C1 actualización de constitución diferida | Cada commit de cambio significativo actualiza constitución y registro de decisiones; la tarea final solo verifica coherencia |
| I1 reintento duplicaba mensajes | Reintento con `attempt_no` y `retry_of_run_id`; reutiliza la pregunta; FR-067 y SC-013 |
| I2 409 sin mecanismo | Índice único parcial `runs(case_id) WHERE status='running'`; liberación en éxito, error, timeout y reinicio; FR-068 y SC-014 |
| I3 transacción durante la generación | Regla de transacciones cortas: ninguna sesión de escritura abierta durante la llamada al modelo |
| I4 `case_id` en el resultado de la herramienta | Eliminado del payload expuesto; se conserva en `run_tool_calls` para trazabilidad |
| O1 `runs` llegaba tarde | Servicio mínimo de ejecución en la fase fundacional; US3 lo usa; US6 añade pasos, fuentes y trazas |
| O2 ingesta de corpus con dependencias incompletas | Reordenada después de extracción, embeddings, índice y orquestación |
| G1 FR-065/FR-066/SC-003 sin tarea | Revisión humana mínima del respaldo semántico, con estados, autor, fecha y observación; sin P1–P4 |

### Tercera ronda (revisión posterior)

Se añadieron el semáforo global de una generación separado de la exclusión por caso, la identidad
local del revisor, el cierre atómico de respuesta, citas y ejecución, y la distinción entre pregunta
nueva, reintento y envío duplicado. El detalle está en § Concurrencia, transacciones y reintentos y
§ Revisión humana del respaldo semántico; la resolución por hallazgo, en
`analysis-2026-11-08.md`.

## Project Structure

### Documentation (this feature)

```text
specs/001-consulta-documental/
├── plan.md                      # Este archivo
├── research.md                  # Fase 0: decisiones y alternativas
├── data-model.md                # Fase 1: entidades, estados e invariantes
├── quickstart.md                # Fase 1: guía de validación prevista
├── contracts/
│   ├── web-routes.md            # Rutas, formularios y respuestas HTML
│   ├── findings-tool.md         # Contrato de la herramienta de hallazgos
│   ├── citations-and-runs.md    # Citas, ejecuciones y trazas
│   └── corpus-manifest.md       # Manifiesto del corpus y procedencia
├── checklists/requirements.md   # Lista de calidad de la especificación
└── tasks.md                     # Fase 2 (/speckit.tasks, aún no generado)
```

### Source Code (repository root)

```text
src/secguard_advisor/
├── __init__.py                  # main() → arranque de uvicorn
├── __main__.py                  # python -m secguard_advisor
├── config.py                    # Settings con pydantic-settings
├── logging.py                   # log estándar con IDs de correlación
├── container.py                 # raíz de composición: construye dependencias
├── db/
│   ├── base.py                  # Base declarativa y utilidades
│   ├── engine.py                # engine, sesión, PRAGMAs
│   ├── transaction.py           # unidad de trabajo de transacción corta
│   └── models.py                # tablas SQLAlchemy
├── cases/
│   ├── service.py               # crear, listar, abrir casos
│   ├── scope.py                 # CaseScope y resolución de alcance
│   └── schemas.py
├── documents/
│   ├── service.py               # alta, deduplicación, versiones, reintento
│   ├── validation.py            # tipo real, tamaño, nombre
│   ├── extraction.py            # pypdf y Markdown a texto por página/sección
│   ├── chunking.py              # fragmentación y presupuesto de tokens
│   ├── embedding.py             # adaptador de embeddings con límite exacto
│   ├── storage.py               # originales content-addressed
│   └── schemas.py
├── retrieval/
│   ├── collections.py           # nombres y registro de colecciones
│   ├── index.py                 # índice Chroma (upsert, borrado, reconstrucción)
│   ├── search.py                # recuperación pública + caso, umbral y fusión
│   ├── citations.py             # construcción y validación de citas
│   └── review.py                # revisión humana del respaldo semántico
├── conversation/
│   ├── graph.py                 # grafo LangGraph y bordes condicionales
│   ├── nodes.py                 # nodos deterministas y nodo agente
│   ├── retry.py                 # reintento de turno e intentos
│   ├── concurrency.py           # una ejecución activa por caso
│   ├── prompts.py               # instrucciones y plantillas de abstención
│   ├── llm.py                   # cliente de generación y esquema de salida
│   ├── memory.py                # checkpointer y reconstrucción de memoria
│   └── schemas.py               # respuesta estructurada del agente
├── tools/
│   ├── findings.py              # herramienta de lectura de hallazgos
│   └── errors.py                # errores de herramienta
├── evidence/
│   ├── runs.py                  # registro de ejecución, pasos y fuentes
│   └── tracing.py               # LangSmith: configuración y estado de traza
├── web/
│   ├── app.py                   # fábrica de la aplicación
│   ├── deps.py                  # dependencias y alcance de caso
│   ├── filters.py               # formato de fechas y estados
│   ├── routes/
│   │   ├── cases.py
│   │   ├── documents.py
│   │   ├── chat.py
│   │   ├── review.py
│   │   └── runs.py
│   ├── templates/
│   │   ├── base.html
│   │   ├── cases/
│   │   ├── documents/
│   │   ├── chat/
│   │   ├── runs/
│   │   └── partials/
│   └── static/
│       ├── css/app.css          # generado por Tailwind, versionado
│       ├── js/htmx.min.js       # vendorizado y fijado
│       ├── js/flowbite.min.js   # vendorizado y fijado
│       └── vendor/MANIFEST.md   # versión, licencia y SHA-256 de cada recurso
├── corpus/
│   ├── acquire.py               # descarga, verificación y manifiesto
│   └── ingest.py                # alta del corpus público
└── seed/
    └── demo.py                  # datos sintéticos deterministas

alembic/                         # migraciones
scripts/
├── fetch_corpus.py              # wrapper de corpus.acquire
├── seed_demo.py                 # wrapper de seed.demo
└── confirm_trace.py             # confirmación de traza observada en LangSmith
data/
├── corpus/
│   ├── originals/               # fuera de Git
│   └── manifest.json            # versionado
└── eval/
    ├── smoke/                   # preguntas de humo, no reservadas
    └── final/                   # reservado; nunca leído por el producto
tests/
├── conftest.py
├── unit/
├── contract/
├── integration/
└── fixtures/
```

**Structure Decision**: un solo proyecto Python con src-layout. La separación exigida por la
constitución se expresa como paquetes con interfaces explícitas, no como servicios desplegables.
La interfaz web (`web/`) depende de los servicios de dominio; ningún servicio importa `web/`.
`container.py` es el único lugar que conoce todas las implementaciones.

## Complexity Tracking

| Decisión | Por qué es necesaria | Alternativa más simple rechazada |
|---|---|---|
| Node.js como herramienta de construcción de CSS | Tailwind y Flowbite exigen compilar; los recursos se sirven localmente | Usar CDN: prohibido por la constitución. Escribir CSS a mano: incumple el stack acordado |
| Adaptador propio de embeddings sobre la API de Ollama | `OllamaEmbeddings` no expone `truncate` ni `prompt_eval_count`; sin ellos no se puede garantizar el límite de 2048 tokens | Usar el wrapper de LangChain: trunca en silencio, justo lo que la constitución prohíbe |
| Una colección vectorial por caso | La constitución prohíbe mezclar datos de casos distintos en una colección | Una sola colección con filtro por metadatos: un filtro mal construido filtra datos de otro caso |
| Checkpointer de LangGraph en base separada | El estado operativo del grafo no debe mezclarse con el estado de negocio | Usar la misma base: acopla el esquema interno de LangGraph con el dominio |

## Auditoría de persistencia

Cada tabla responde a un requisito, una invariante o una necesidad de recuperación de **este**
incremento. Se revisaron las 18 tablas del diseño inicial y se aplicaron dos simplificaciones
antes de implementar.

| Tabla | Función en el incremento |
|---|---|
| `cases` | H1; FR-001..FR-007 |
| `assets` | H1 y H5; hallazgos por activo |
| `documents` | H2; identidad lógica y separación de origen |
| `document_versions` | H2; deduplicación, versiones y estados |
| `document_chunks` | H2/H3; procedencia, localización y reindexación |
| `ingestion_jobs` | H2; reintento y recuperación tras interrupción |
| `conversations` | H4; una por caso |
| `messages` | H4; historial visible |
| `message_citations` | H3; citas y control humano |
| `runs` | H6; evidencia de ejecución |
| `run_steps` | H6; distinción entre pasos deterministas y del modelo |
| `run_sources` | H6; fuentes recuperadas |
| `run_tool_calls` | H5/H6; herramienta y origen de la invocación |
| `synthetic_datasets` | H5; procedencia y checksum del seed |
| `findings` | H5; datos consultables |
| `finding_cves` | H5; filtro exacto por CVE |

**Simplificaciones aplicadas antes de implementar:**

- **`corpus_sources` eliminada.** `data/corpus/manifest.json` es la fuente de bibliografía,
  licencia y versión; `documents.source_id` referencia su identificador y se valida al arrancar.
  Mantener una tabla duplicaba la misma información en dos lugares.
- **`vector_collections` eliminada.** El nombre de la colección se deriva de forma determinista en
  `retrieval/collections.py` a partir del alcance, el modelo y la dimensión; el conteo se obtiene de
  `document_chunks`. No hacía falta persistir un registro que se puede recalcular.

Resultado: **16 tablas** justificadas. `data-model.md`, `research.md` y
`contracts/corpus-manifest.md` se sincronizaron con estas simplificaciones.

## Concurrencia, transacciones y reintentos

Hay **dos controles distintos** y no deben confundirse:

1. **Exclusión por caso** (persistida): un índice único parcial sobre `runs(case_id)` cuando
   `status='running'`. Una segunda consulta del mismo caso no se encola: se rechaza con un mensaje
   claro. La adquisición es atómica: si dos peticiones compiten, una inserta y la otra recibe el
   conflicto.
2. **Límite global de generación** (en proceso): un semáforo de un permiso que envuelve la llamada
   al modelo. Se adquiere **antes** de crear la ejecución, con espera acotada
   (`SECGUARD_GENERATION_QUEUE_TIMEOUT_SECONDS`). Si no se adquiere, la petición se rechaza sin
   crear ejecución ni mensaje. El semáforo se libera en `finally`, después de persistir el
   resultado, nunca al desconectarse el cliente.

**Un solo proceso y un worker.** El semáforo es local al proceso y la reconciliación de arranque
asume que no hay otro proceso escribiendo. Los comandos de ejecución fijan `--workers 1`.

**Desconexión del cliente.** Los manejadores son síncronos y no se cancelan al cortarse la conexión:
la generación continúa, la ejecución conserva el bloqueo por caso y el semáforo global, y se libera
solo al terminar o agotar el tiempo. Un timeout del cliente no habilita generaciones ilimitadas.

**Transacciones.** Secuencia obligatoria:

1. `T1`: adquirir el semáforo global; crear `runs` (`running`, `attempt_no`) y el mensaje de usuario
   en una transacción corta. Si falla la exclusión por caso, liberar el semáforo y responder `409`.
2. Sin transacción ni sesión abierta: recuperación y generación.
3. `T2`: persistir **en una sola transacción** el mensaje asistente, sus citas y controles, los
   pasos, las fuentes, las llamadas a herramientas y el **cierre de la ejecución** (`status`,
   `outcome`, `duration_ms`, `finished_at`, `answer_message_id`).
4. Si `T2` falla: no hay respuesta persistida. Se intenta cerrar la ejecución como `failed` en una
   transacción best-effort; si también falla, el arranque la marca `interrupted`. Liberar el
   semáforo en `finally`.

**Reintento idempotente.** Solo se reintenta una ejecución `failed`, `timeout` o `interrupted` **y
sin respuesta persistida**. Se reutiliza el mensaje de pregunta, se crea un `runs` nuevo con
`attempt_no` y `retry_of_run_id`, y no se duplican mensajes ni efectos. Un turno exitoso no se
reintenta. Un envío duplicado mientras hay una ejecución activa se rechaza sin crear mensaje; un
envío repetido después de un turno exitoso es una pregunta nueva.

**Checkpoints separados.** El checkpointer de LangGraph vive en otra base SQLite. No se promete
atomicidad entre ambas bases. Los mensajes de la base de aplicación son la fuente autoritativa; el
checkpoint es memoria operativa y se reconcilia desde los mensajes antes de cada turno. Si el
checkpoint quedó adelantado por un fallo, se recorta; si falta, se reconstruye.

## Revisión humana del respaldo semántico

El control automático de cita prueba existencia, localización y coincidencia literal. No prueba que
el fragmento sostenga la afirmación.

Se añade una revisión humana mínima por cita:

- estados `unreviewed`, `supported`, `not_supported`;
- autor, fecha y observación opcional;
- el autor proviene de `SECGUARD_REVIEWER_NAME`; sin esa configuración no se guarda la revisión y
  se responde con un error claro;
- `SECGUARD_REVIEWER_NAME` es una identidad local declarada, no un mecanismo de autenticación;
- visible en la respuesta y en la ejecución, separada del control automático;
- no incluye adjudicación P1–P4, aprobación de informes ni exportación.

Una cita `valid` con revisión `unreviewed` no se presenta como fundamentada. SC-003 se acredita con
esta revisión, no con el control automático.

## Fases de diseño

### Fase 0 — Investigación

Ver `research.md`. Resuelve: límite exacto de tokens de embeddings, estrategia de citas
verificables, aislamiento de memoria, formato de salida del modelo, construcción de recursos de
interfaz, idempotencia de ingesta y separación del conjunto de evaluación. No queda ninguna
ambigüedad abierta.

### Fase 1 — Diseño

Ver `data-model.md`, `contracts/` y `quickstart.md`.

## Estrategia de construcción

Cortes pequeños, cada uno con su código, sus pruebas y su documentación. El recorrido se vuelve
demostrable de forma progresiva, pero la aceptación exige las seis historias.

| Corte | Contenido | Historias | Verificación |
|---|---|---|---|
| C0 | Scaffolding de calidad: Makefile, pre-commit, Ruff, pytest, CI, layout y configuración | — | `make check` en verde |
| C1 | Persistencia, migraciones, `CaseScope` y creación/reapertura de casos | H1 | Unitarias + contrato de rutas |
| C2 | Validación, extracción, deduplicación, versiones y estados de ingesta | H2 | Unitarias con PDFs de fixture |
| C3 | Fragmentación, embeddings con límite exacto, índice y reconstrucción | H2 | Integración con EmbeddingGemma |
| C4 | Recuperación, citas validadas y respuesta con abstención | H3 | Integración con generador real |
| C5 | Grafo, memoria persistente y aislamiento entre casos | H4 | Integración + reinicio |
| C6 | Herramienta de hallazgos, seed determinista y conteos | H5 | Unitarias de herramienta + integración |
| C7 | Registro de ejecución, pasos, fuentes y trazas | H6 | Integración + inspección de traza |
| C8 | Recorrido de demostración y guía de validación | Todas | Recorrido manual reproducible |

## Estrategia de commits

Conventional Commits, sin atribución de IA, un corte por commit revisable cuando el corte lo
permita. Los commits se crean en la rama de la funcionalidad; el repositorio aún no tiene
commits y no se modifica la configuración global de Git.

```text
chore: scaffold quality tooling and package layout
feat: add configuration and persistence foundation
feat: create and reopen cases with scoped access
feat: ingest documents with provenance and deduplication
feat: index and retrieve fragments with verifiable citations
feat: converse with persistent per-case memory
feat: query synthetic findings through a scoped tool
feat: record run evidence and real traces
test: cover the acceptance journey end to end
docs: document architecture and demo walkthrough
```

Cada commit debe dejar `make check` en verde. Las pruebas de integración se ejecutan antes de
declarar terminado un corte, aunque no formen parte del job rápido de CI.

## Riesgos concretos

1. **Tokenización exacta de EmbeddingGemma.** El modelo está bajo licencia Gemma y su tokenizer
   no está disponible localmente sin aceptar condiciones. Mitigación: `truncate: false` en la API
   de Ollama convierte un exceso de tokens en error, y `prompt_eval_count` devuelve el conteo
   exacto. Se usa el propio modelo como oráculo; no se estima a ciegas.
2. **Latencia del generador de 9B.** Un turno puede acercarse al límite de 60 s en hardware
   modesto. Mitigación: contexto acotado, `num_predict` limitado, una sola llamada al modelo por
   turno salvo reparación de citas, y timeout explícito.
3. **Extracción de PDF.** Tablas y apéndices del corpus pueden extraerse mal. Mitigación:
   reporte de páginas no legibles, verificación de extracción por documento y rechazo explícito
   cuando no hay texto utilizable.
4. **Crecimiento de colecciones por caso.** Aceptable en este incremento; se registra como
   límite de escala y se revisará si el número de casos crece.
5. **Deriva entre checkpointer y mensajes.** Mitigación: la conversación visible se lee de
   SQLite; el checkpointer solo aporta memoria operativa y se reconstruye desde los mensajes si
   falta.
6. **Trazas declaradas sin verificación.** Mitigación: la traza se marca `submitted` solo tras
   `flush` sin error; la aceptación exige verla en LangSmith, no confiar en el estado local. La
   confirmación es responsabilidad de la persona que ejecuta la aceptación, con identidad, fecha y
   evidencia registradas.

## Dependencias

- Corpus del incremento 1 descargado y verificado (pendiente, no se declara hecho).
- Ollama con `qwen3.5:9b` y `embeddinggemma` (verificado).
- LangSmith configurado con traza real (verificado; el proyecto se crea al primer envío).
- Herramientas de construcción de CSS (Node) instaladas solo para desarrollo.
- Sin dependencia de Qualys, P1–P4 ni presupuesto externo.

## Resultado esperado de esta fase

`plan.md`, `research.md`, `data-model.md`, `contracts/` y `quickstart.md`. No se generan tareas
ni código de aplicación.
