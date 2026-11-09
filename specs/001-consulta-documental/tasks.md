---

description: "Task list for feature 001 implementation"
---

# Tasks: Consulta documental con evidencias, memoria por caso y hallazgos

**Input**: Diseño de `specs/001-consulta-documental/` (spec, plan, research, data-model, contracts,
quickstart)

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Incluidas. La constitución exige test-first por defecto y el encargo pide pruebas por
historia. Cada bloque de pruebas se escribe y se observa en rojo antes de su implementación.

**Organization**: Fases por historia de usuario. Las seis historias son necesarias para aceptar el
incremento; la prioridad ordena el trabajo, no permite omitir ninguna.

## Reconciliación aplicada

### Primera ronda (correcciones del plan)

1. **FR-020** se limitó a evidencias privadas. El corpus público es compartido y no pertenece a
   ningún caso.
2. **SC-003** se separó en control automático y revisión humana registrada. Se añadieron FR-065 y
   FR-066.
3. **Abstención**: la recuperación vacía no corta el turno; el agente se ejecuta con la herramienta
   y la abstención se decide después. El umbral es un filtro calibrable.
4. **Persistencia**: 16 tablas justificadas; se eliminaron `corpus_sources` y
   `vector_collections`.

### Segunda ronda (revisión de consistencia)

| Hallazgo | Resolución en este archivo |
|---|---|
| C1 gobierno diferido | Cada commit significativo actualiza constitución y decisiones; T093 solo verifica |
| I1 reintento duplicaba mensajes | T063: intento nuevo, misma pregunta, sin mensaje duplicado; FR-067/SC-013 |
| I2 409 sin mecanismo | T059: guardián por caso con índice único parcial y liberación; FR-068/SC-014 |
| I3 transacción durante la generación | T022: unidad de trabajo de transacción corta; ninguna sesión abierta durante el modelo |
| I4 `case_id` expuesto al modelo | T076: resultado sin `case_id`; traza interna en `run_tool_calls` |
| O1 `runs` llegaba tarde | T027: servicio mínimo de ejecución en la fase fundacional; T082 expone las consultas de evidencia |
| O2 corpus con dependencias incompletas | T045–T046 reordenadas después de extracción, embeddings, índice y orquestación |
| G1 FR-065/066/SC-003 sin tarea | T064: revisión humana mínima; T085 muestra ambos controles; T068 la prueba |
| I5 originales no ignorados | `.gitignore` corregido; T001 lo verifica |
| I6 CI en rojo sin pruebas | T010 prueba de humo antes de T011 |
| I7 `npm ci` sin lockfile | T007 genera y versiona `package-lock.json` |
| I8 `AGENTS.md` inexistente | T004 lo crea |
| I9 sin guardia de referencias | T026 cubre `docs/referencias`, constitución e instrucciones |
| I10 fallo a mitad de turno | T074 prueba consistencia mensajes/checkpoint/ejecución |
| U1 ejecución no mostraba ambos controles | T085 muestra control automático y revisión humana |
| O3 arnés dependía de la fábrica | T009 solo fixtures de base; el fixture de app llega en T019 |
| O4 pruebas sin dependencia de corpus | T065, T066 y T090 declaran T046 |
| O5 paralelismo mal anotado | Sección de paralelismo corregida |
| D1 T088 podía duplicar plantillas | T088 acotada a layout y navegación |
| A1 `verified` vs `confirmed` | `confirmed` es el único estado; «verificada» solo como prosa |
| U2 fragmentos recuperados implícitos | T061 exige mostrar fragmentos usados y su procedencia |
| I11 README con funciones no implementadas | T012 separa «Implementado» y «Previsto» |
| I12 README vacío en el primer commit | T001 commitea un README mínimo con estado |
| I13 | targets sin script | T003 hace que los targets informen «no implementado» |

### Tercera ronda (revisión posterior)

| Hallazgo | Resolución en este archivo |
|---|---|
| N1 límite global no aplicado | T059: semáforo global de una generación, separado de la exclusión por caso; T061 responde `429` |
| N2 autor de revisión sin fuente | T013 configura `SECGUARD_REVIEWER_NAME`; T064 rechaza sin identidad; T068 lo prueba |
| N3 respuesta y cierre no atómicos | T027 expone el cierre transaccional; T061 persiste respuesta, citas, telemetría y cierre en una transacción; T063 exige ausencia de respuesta para reintentar |
| N4 proceso/worker | T003 fija `--workers 1`; T011 CI y T012 lo documentan |
| N5 alcance de mensajes y citas | T064 y T068 validan `message_id` y `citation_id` dentro del caso |
| N6 desconexión del cliente | T059 prueba que la liberación no ocurre antes del cierre real |
| N7 confirmación de traza | T091 usa `scripts/confirm_trace.py` con verificación por API de lectura |
| N8 tres tipos de solicitud | T063 distingue pregunta nueva, reintento y envío duplicado |

## Format: `[ID] [P?] [Story] Description`

- **[P]**: puede ejecutarse en paralelo (archivos distintos, sin dependencias pendientes)
- **[Story]**: historia a la que pertenece la tarea
- Cada tarea declara `Dep`, `Check` y `Evidence`

## Cortes funcionales

| Corte | Fases | Contenido |
|---|---|---|
| 1. Base, configuración y calidad | 1 y 2 | Repositorio, tooling, configuración, persistencia, seed |
| 2. Caso y seed | 2 y 3 | Esquema, alcance, caso, datos sintéticos, ejecución mínima |
| 3. Corpus, ingesta e índice | 4 | Adquisición, extracción, fragmentación, embeddings, Chroma |
| 4. Consulta con recuperación y citas | 5 | Recuperación, generación, citas, revisión humana, abstención |
| 5. Memoria y herramienta | 6 y 7 | Checkpoints, aislamiento, herramienta de hallazgos |
| 6. Interfaz integrada y errores | 8 y 9 | Evidencia de ejecución, navegación, estados |
| 7. Aceptación y demo | 9 | Recorrido completo, integración real, documentación |

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: repositorio, calidad y estructura base. Sin esto no hay verificación posible.

- [X] T001 Crear la rama `001-consulta-documental` y el commit inicial — `git switch -c 001-consulta-documental`; incluir `docs/`, `specs/`, `.specify/`, `CONSTITUTION.md`, `README.md` mínimo con sección «Estado», `.env.example`, `.gitignore` (con `data/corpus/originals/`), `.agents/`, `.opencode/`, `skills-lock.json`, `pyproject.toml`, `uv.lock`, `.python-version`; excluir `.env`, `.atl/`, `storage/` · Dep: ninguna · Check: `git check-ignore .env data/corpus/originals/x.pdf` y `git log --oneline -1` · Evidence: rama, hash y verificación de ignorados
- [X] T002 [P] Completar metadatos y calidad en `pyproject.toml` — descripción real, `requires-python`, Ruff (lint + format), pytest (`testpaths`, marcador `integration`, sin fallar por colección vacía) · Dep: T001 · Check: `uv sync` y `uv run ruff check .` · Evidence: salida de ambos
- [X] T003 [P] Crear `Makefile` — `help`, `install`, `assets`, `corpus`, `seed-demo`, `dev`, `demo`, `lint`, `format`, `test`, `test-integration`, `check`, `clean`; `dev` y `demo` fijan `--workers 1`; los targets sin script informan «no implementado» y salen con código distinto de cero · Dep: T001 · Check: `make help`, `make corpus` informa y `make -n dev` muestra `--workers 1` · Evidence: salidas
- [X] T004 [P] Añadir `.editorconfig`, `LICENSE` (MIT), `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` y `AGENTS.md` · Dep: T001 · Check: archivos presentes y coherentes con el estándar · Evidence: revisión de contenido
- [X] T005 [P] Configurar `.pre-commit-config.yaml` — higiene, Ruff, `uv-lock` · Dep: T002 · Check: `uv run pre-commit run --all-files` · Evidence: salida del hook
- [X] T006 [P] Crear el esqueleto en `src/secguard_advisor/` — `__init__.py` con `__version__`, `__main__.py`, subpaquetes de `plan.md` § Source Code · Dep: T001 · Check: `uv run python -c "import secguard_advisor"` · Evidence: import exitoso
- [X] T007 [P] Preparar recursos de interfaz — `package.json` con Tailwind/Flowbite fijados, `package-lock.json` generado y versionado, `tailwind.config.js`, `htmx.min.js` y `flowbite.min.js` vendorizados, `static/vendor/MANIFEST.md` con versión, licencia y SHA-256 reales · Dep: T006 · Check: `npm ci` y compilación de `static/css/app.css` · Evidence: lockfile, CSS y manifiesto con hashes calculados
- [X] T008 [P] Implementar logging en `src/secguard_advisor/logging.py` — formato con `run_id`, `case_id`, `event`; sin secretos · Dep: T006 · Check: `tests/unit/test_logging.py` · Evidence: test en verde
- [X] T009 [P] Crear el arnés de pruebas en `tests/conftest.py` — base SQLite temporal, directorio de almacenamiento temporal, marcador `integration`; **sin** fábrica de aplicación · Dep: T006 · Check: `uv run pytest --collect-only` · Evidence: colección correcta
- [X] T010 [P] Añadir prueba de humo en `tests/unit/test_package_smoke.py` — importación del paquete y `__version__` · Dep: T006 · Check: `uv run pytest tests/unit/test_package_smoke.py` · Evidence: test en verde
- [X] T011 Crear gobernanza de GitHub en `.github/` — PR con verificación de constitución, issues, `labels.yml`, `dependabot.yml`, `ci.yml` con paridad a `make check` · Dep: T002, T003, T010 · Check: `make check` ejecutado localmente antes de declarar CI · Evidence: workflow y salida local
- [X] T012 Escribir `README.md` profesional con secciones «Implementado» y «Previsto» — propósito, funcionalidades, arquitectura, instalación, configuración, ejecución, pruebas, estructura y licencia; badges solo verificables (Python, licencia); sin badge de CI hasta definir repositorio · Dep: T002, T004 · Check: revisión de enlaces y de que nada previsto se presenta como implementado · Evidence: README revisado


**Evidencia del corte (2026-11-08)**

- `uv sync --locked`: 133 paquetes resueltos, 131 comprobados, sin error.
- `make check`: Ruff sin hallazgos, formato correcto y 4 pruebas ejecutadas en verde.
- `uv run pytest -q`: 4 passed.
- `npm ci` y `npm run build`: exit 0; `git diff --exit-code -- src/secguard_advisor/web/static` sin cambios.
- `git check-ignore`: `.env`, `data/corpus/originals/` y `.atl/` ignorados.
- `uv run pre-commit run --all-files`: todos los hooks en verde.
- `make -n dev`: muestra `--workers 1`.
- `make corpus`: informa «no implementado: requiere T045» y sale con error.
- CI: workflow preparado; no ejecutado en GitHub por falta de remoto.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: configuración, persistencia, alcance, arranque, transacciones, datos sintéticos y
ejecución mínima. Bloquea todas las historias.

**⚠️ CRITICAL**: ninguna historia comienza hasta completar esta fase.

- [X] T013 Implementar configuración en `src/secguard_advisor/config.py` — `pydantic-settings`, `SecretStr`, rutas, modelos, `num_ctx`, límites de turno y archivo, umbral de recuperación, `SECGUARD_REVIEWER_NAME` y `SECGUARD_GENERATION_QUEUE_TIMEOUT_SECONDS` · Dep: T006 · Check: `tests/unit/test_config.py` (incluye identidad de revisor vacía y espera acotada) · Evidence: test en verde
- [X] T014 Crear `src/secguard_advisor/db/base.py` y `engine.py` — Base, engine SQLite, `foreign_keys=ON`, WAL, `busy_timeout`, fábrica de sesiones · Dep: T013 · Check: `tests/unit/test_db_engine.py` · Evidence: PRAGMAs verificados
- [X] T015 Definir las 16 tablas en `src/secguard_advisor/db/models.py` — según `data-model.md`, con `UNIQUE(scope_key, sha256)`, `UNIQUE(version_id, chunk_index)`, `UNIQUE(question_message_id, attempt_no)` e índice único parcial `runs(case_id) WHERE status='running'` · Dep: T014 · Check: `tests/unit/test_schema.py` (restricciones rechazan filas inválidas y segunda ejecución activa) · Evidence: test en verde
- [X] T016 Configurar Alembic en `alembic/` y migración inicial · Dep: T015 · Check: `alembic upgrade head` y `alembic downgrade base` · Evidence: migración reversible
- [X] T017 Implementar `CaseScope` en `src/secguard_advisor/cases/scope.py` — desde la ruta, valida existencia, no acepta `case_id` por cuerpo ni consulta · Dep: T016 · Check: `tests/unit/test_case_scope.py` · Evidence: test en verde
- [X] T018 Implementar reconciliación de arranque en `src/secguard_advisor/db/recovery.py` — `runs.running → interrupted` (libera el caso), `ingestion_jobs.running → interrupted`, `document_versions.processing → failed(interrupted)` · Dep: T016 · Check: `tests/unit/test_startup_recovery.py` · Evidence: test en verde
- [X] T019 Crear la fábrica en `src/secguard_advisor/web/app.py` — routers, estáticos, manejadores de error, validación de origen, loopback, `/healthz`; añadir el fixture de aplicación en `tests/conftest.py` · Dep: T013, T017, T009 · Check: `tests/contract/test_app_shell.py` (404, 403 de origen, `/healthz`) · Evidence: test en verde
- [X] T020 Crear plantillas base en `src/secguard_advisor/web/templates/base.html` y parciales de error — español, navegación, recursos locales · Dep: T007, T019 · Check: `tests/contract/test_templates.py` (sin URLs externas) · Evidence: test en verde
- [X] T021 Implementar taxonomía de errores en `src/secguard_advisor/web/errors.py` — código, estado HTTP y mensaje en español; sin trazas internas · Dep: T019 · Check: `tests/unit/test_error_messages.py` · Evidence: test en verde
- [X] T022 Implementar la unidad de trabajo en `src/secguard_advisor/db/transaction.py` — transacción corta, cierre explícito y aserción de que no hay transacción activa antes de llamar al modelo · Dep: T014 · Check: `tests/unit/test_transaction_scope.py` · Evidence: test en verde
- [X] T023 Implementar generación determinista de datos sintéticos en `src/secguard_advisor/seed/demo.py` — caso de demostración, activos y hallazgos con semilla fija, checksum SHA-256, `is_synthetic` · Dep: T015 · Check: `tests/unit/test_seed_demo.py` (mismo checksum en dos ejecuciones) · Evidence: checksum idéntico
- [X] T024 Crear `scripts/seed_demo.py` y el target `make seed-demo` · Dep: T023 · Check: ejecución doble idempotente · Evidence: conteos antes y después
- [X] T025 Crear dobles de prueba en `tests/fixtures/` — embeddings falsos deterministas, generador falso con JSON controlado, PDFs (textual, escaneado, corrupto) y Markdown con instrucciones incrustadas · Dep: T009 · Check: usados por pruebas unitarias · Evidence: pruebas que los usan
- [X] T026 Extender la guardia de aislamiento — `data/eval/final/` reservado y ninguna referencia, desde `src/secguard_advisor`, a `docs/referencias/`, `CONSTITUTION.md`, instrucciones de agentes ni respuestas esperadas de pruebas · Dep: T006 · Check: `tests/unit/test_corpus_isolation.py` · Evidence: test en verde
- [X] T027 Implementar el ciclo de vida mínimo de ejecución en `src/secguard_advisor/evidence/runs.py` — crear `runs` (`running`, `attempt_no`), cierre transaccional que participa en una transacción existente (respuesta, citas, telemetría y cierre), cierre en éxito/error/timeout, marcar interrumpida, mapear la violación del índice único a «consulta en curso» · Dep: T015, T022 · Check: `tests/unit/test_run_lifecycle.py` (el cierre no confirma por sí solo y no deja respuesta sin cierre) · Evidence: test en verde

**Checkpoint**: fundación lista; las historias pueden comenzar.


**Evidencia del corte (2026-11-08)**

- `uv sync --locked`: 133 paquetes resueltos, 131 comprobados, sin error.
- `uv run alembic upgrade head` y `downgrade base` sobre almacenamiento temporal: 16 tablas de aplicación y `alembic_version`; el índice parcial `ux_runs_one_active_per_case` existe; el downgrade deja solo `alembic_version`.
- `uv run pytest -q`: 55 pruebas en verde.
- `make check`: Ruff sin hallazgos, formato correcto y 55 pruebas.
- `uv run pre-commit run --all-files`: todos los hooks en verde.
- `make seed-demo` dos veces con esquema migrado: «creado» y «ya existía»; 1 caso, 3 activos, 12 hallazgos, 1 dataset.
- Servidor real con `uvicorn --factory ... --workers 1`: `GET /healthz` → 200 `{"status":"ok","database":"ok","ollama":"ok"}`; `/static/css/app.css` → 200.
- `npm ci` y `npm run build`: exit 0; recursos reproducibles sin cambios.
- `git check-ignore`: `.env`, `data/corpus/originals/` y `.atl/` ignorados.

---

## Phase 3: User Story 1 - Crear y recuperar un caso (Priority: P1) 🎯 MVP

**Goal**: caso con contexto, campos desconocidos explícitos y persistencia tras reinicio.

**Independent Test**: crear un caso con dos campos vacíos, reiniciar y reabrirlo; el contexto coincide y los vacíos siguen marcados como desconocidos.

### Tests for User Story 1

- [X] T028 [P] [US1] Pruebas unitarias del servicio en `tests/unit/test_cases_service.py` — título obligatorio, campos desconocidos, activos, marca sintética · Dep: T017 · Check: fallan antes de T030 · Evidence: rojo y verde
- [X] T029 [P] [US1] Pruebas de contrato en `tests/contract/test_cases_routes.py` — listado, formulario, creación, detalle, 422 sin título, 404 de caso ajeno · Dep: T019 · Check: fallan antes de T031 · Evidence: rojo y verde

### Implementation for User Story 1

- [X] T030 [US1] Implementar esquemas y servicio en `src/secguard_advisor/cases/schemas.py` y `service.py` — crear, listar, abrir; nunca completar vacíos · Dep: T028 · Check: T028 en verde · Evidence: test en verde
- [X] T031 [US1] Implementar rutas y plantillas en `src/secguard_advisor/web/routes/cases.py` y `templates/cases/` · Dep: T029, T030 · Check: T029 en verde · Evidence: test en verde
- [X] T032 [US1] Prueba de persistencia tras reinicio en `tests/integration/test_case_persistence.py` — base en archivo, reapertura · Dep: T030 · Check: caso y activos intactos · Evidence: test en verde
- [X] T033 [US1] Mostrar marca educativa y campos desconocidos en `templates/cases/detail.html` · Dep: T031 · Check: aserciones sobre HTML · Evidence: test en verde


**Evidencia de US1 (2026-11-08)**

- `uv run pytest tests/unit/test_cases_service.py`: 9 pruebas en verde.
- `uv run pytest tests/contract/test_cases_routes.py`: 11 pruebas en verde.
- `uv run pytest tests/contract/test_case_detail.py`: 2 pruebas en verde.
- `uv run pytest tests/integration/test_case_persistence.py`: 1 prueba en verde.
- `make check`: 78 pruebas en verde, Ruff y formato correctos.
- Servidor real (uvicorn, un worker, almacenamiento temporal): `POST /cases` → 303; `GET /cases/{id}` → 200 con título, contexto, activos y campo desconocido; reinicio del servidor → `GET /cases/{id}` → 200 con título y activos intactos.
- `npm run build`: CSS regenerado y reproducible.
- Revisión visual en navegador: pendiente; no hay navegador disponible. Se verificó estructura HTML, clases locales, escape de contenido y estados vacíos.

**Checkpoint**: US1 funcional y verificable por separado.

---

## Phase 4: User Story 2 - Incorporar documentos (Priority: P1)

**Goal**: corpus público adquirido y verificado, documentos de caso validados, procesados, deduplicados, versionados e indexados con procedencia.

**Independent Test**: cargar un PDF textual, un Markdown, un PDF escaneado y un archivo corrupto; verificar estados y que solo los dos primeros sean consultables.

### Tests for User Story 2

- [X] T034 [P] [US2] Pruebas de validación en `tests/unit/test_document_validation.py` — extensión, magic bytes, tamaño, extensión falsa · Dep: T025 · Check: fallan antes de T039 · Evidence: rojo y verde
- [X] T035 [P] [US2] Pruebas de extracción en `tests/unit/test_extraction.py` — PDF textual, escaneado, Markdown, páginas no legibles · Dep: T025 · Check: fallan antes de T040 · Evidence: rojo y verde
- [X] T036 [P] [US2] Pruebas de fragmentación en `tests/unit/test_chunking.py` — presupuesto, solape, página y sección, sin truncamiento · Dep: T025 · Check: fallan antes de T041 · Evidence: rojo y verde
- [X] T037 [P] [US2] Pruebas de deduplicación y versiones en `tests/unit/test_document_versions.py` — mismo `sha256` no duplica, contenido distinto crea versión, anterior superada · Dep: T015 · Check: fallan antes de T044 · Evidence: rojo y verde
- [X] T038 [P] [US2] Pruebas de contrato en `tests/contract/test_documents_routes.py` — carga, 409, 413, 415, detalle, reintento · Dep: T019 · Check: fallan antes de T048 · Evidence: rojo y verde

### Implementation for User Story 2

- [X] T039 [US2] Implementar validación y almacenamiento en `src/secguard_advisor/documents/validation.py` y `storage.py` — tipo real, tamaño, hash en streaming, originales content-addressed · Dep: T034 · Check: T034 en verde · Evidence: test en verde
- [X] T040 [US2] Implementar extracción en `src/secguard_advisor/documents/extraction.py` — pypdf por página, Markdown por sección, `unreadable_pages`, `no_usable_text` · Dep: T035 · Check: T035 en verde · Evidence: test en verde
- [X] T041 [US2] Implementar fragmentación en `src/secguard_advisor/documents/chunking.py` — unidades por página/sección, presupuesto conservador, offsets y locator · Dep: T036 · Check: T036 en verde · Evidence: test en verde
- [X] T042 [US2] Implementar el adaptador de embeddings en `src/secguard_advisor/documents/embedding.py` — `/api/embed` con `truncate: false`, **una entrada por petición**, `prompt_eval_count` como `token_count`, prefijos oficiales · Dep: T013 · Check: `tests/unit/test_embedding_adapter.py` con transporte falso · Evidence: test en verde y `token_count_source`
- [X] T043 [US2] Implementar colecciones e índice en `src/secguard_advisor/retrieval/collections.py` e `index.py` — nombres derivados del alcance autorizado, validación de formato, `upsert` por `chunk_id`, reconstrucción · Dep: T019, T042 · Check: `tests/unit/test_collections.py` y `tests/integration/test_index_rebuild.py` · Evidence: test en verde
- [X] T044 [US2] Implementar la orquestación de ingesta en `src/secguard_advisor/documents/service.py` — estados, trabajo, deduplicación, versión, idempotencia por `(version_id, chunk_index)` · Dep: T037, T039, T040, T041, T043 · Check: T037 en verde · Evidence: test en verde
- [X] T045 [US2] Implementar adquisición del corpus en `src/secguard_advisor/corpus/acquire.py` y `scripts/fetch_corpus.py` — descarga oficial, SHA-256 y bytes calculados al descargar, manifiesto, verificación de páginas con texto; sin hashes inventados · Dep: T039, T040 · Check: `make corpus` sobre las cuatro fuentes y segunda ejecución idempotente · Evidence: manifiesto con hashes reales
- [X] T046 [US2] Implementar la ingesta del corpus público en `src/secguard_advisor/corpus/ingest.py` — alta como `public_corpus` sin caso, `source_id` validado contra el manifiesto · Dep: T044, T045 · Check: documentos públicos sin `case_id` y citables · Evidence: consulta a la base
- [X] T047 [US2] Implementar reintento e interrupción de ingesta en `documents/service.py` y `POST /cases/{case_id}/documents/{document_id}/retry` — reutiliza texto, no duplica, nunca deja `available` a medias · Dep: T044, T018 · Check: `tests/unit/test_ingestion_recovery.py` · Evidence: test en verde
- [X] T048 [US2] Implementar rutas y plantillas de documentos en `src/secguard_advisor/web/routes/documents.py` y `templates/documents/` — estados, versiones, reintento, visor de fragmento · Dep: T038, T044 · Check: T038 en verde · Evidence: test en verde
- [X] T049 [US2] Prueba de ingesta real en `tests/integration/test_ingestion_real.py` — EmbeddingGemma, tokens por fragmento ≤ 2048 medidos individualmente, índice poblado · Dep: T042, T043, T044 · Check: `make test-integration` · Evidence: salida con conteos reales
- [X] T050 [US2] Pruebas de reimportación y versiones en `tests/integration/test_reimport_versions.py` — idéntico no duplica; modificado crea versión; cita antigua resuelve · Dep: T047 · Check: conteos y resolución · Evidence: test en verde
- [X] T051 [US2] Prueba de instrucciones maliciosas en `tests/integration/test_prompt_injection.py` — no altera comportamiento ni produce acciones · Dep: T040 · Check: respuesta sin efecto · Evidence: test en verde


**Evidencia de US2 (2026-11-08)**

- `pytest` unitario: validación 10, extracción 6, fragmentación 4, embeddings 6, colecciones 6, versiones 9, corpus 4; índice 2.
- `pytest` de contrato de documentos: 9.
- `pytest -m integration`: 2 pruebas reales con EmbeddingGemma y Chroma.
- `pytest tests/integration/test_prompt_injection.py`: 1.
- `make check`: 135 pruebas en verde, 2 deseleccionadas; Ruff y formato correctos.
- `make corpus`: cuatro fuentes verificadas con SHA-256 y páginas reales (csf2 32, airmf 48, ai6001 64, owasp 45); `--verify-only` repetido sin cambios. Una segunda ejecución reutiliza el original local verificado sin descargar ni reescribir el manifiesto; `--refresh` fuerza la descarga.
- `make corpus-ingest`: 4 documentos públicos, 4 versiones disponibles, 193 fragmentos; máximo de 1440 tokens por fragmento; colección pública de Chroma con 193 vectores; segunda ejecución devuelve «duplicate» para las cuatro fuentes.
- Consulta real del índice con EmbeddingGemma: devuelve fragmentos del CSF 2.0 con distancias y localizadores.
- Servidor real con almacenamiento temporal: caso 303, carga de PDF 201 «Disponible», detalle 200 «Versiones»; reinicio del servidor y caso 200 con el documento.
- `npm run build`: CSS regenerado y reproducible.
- Revisión visual en navegador: pendiente; no hay navegador disponible.
- Comprobación inicial de US3 con datos reales (2026-11-08): recuperación pertinente de las cuatro fuentes públicas (csf2 p:2#1, airmf p:3#2, ai6001 p:2#1, owasp p:16#17), con título, versión `available`, localizador y texto del índice idéntico al persistido en SQLite; reconstrucción de una colección Chroma temporal desde los 193 fragmentos persistidos, con consulta posterior pertinente y sin tocar el almacenamiento habitual. La exclusión de versiones superadas y el aislamiento entre casos son propiedades de la recuperación (T055) y quedaron fijadas por T053.

**Checkpoint**: US2 funcional; corpus e ingesta verificables.

---

## Phase 5: User Story 3 - Preguntar y comprobar fuentes (Priority: P1)

**Goal**: respuesta en español con citas verificables, distinción hecho/recomendación/insuficiencia, revisión humana del respaldo y abstención cuando no hay respaldo.

**Independent Test**: preguntar algo cubierto por los documentos y comprobar que la cita abre el fragmento; preguntar algo sin respaldo y comprobar la abstención.

### Tests for User Story 3

- [X] T052 [P] [US3] Pruebas del validador de citas en `tests/unit/test_citation_validator.py` — existencia, versión, cita literal, página/sección, rechazo con motivo · Dep: T015 · Check: fallan antes de T056 · Evidence: rojo y verde
- [X] T053 [P] [US3] Pruebas de recuperación en `tests/unit/test_retrieval.py` — fusión público/caso, umbral como filtro, vacío no concluyente, sin mezcla · Dep: T043 · Check: fallan antes de T055 · Evidence: rojo y verde
- [X] T054 [P] [US3] Pruebas de contrato del chat en `tests/contract/test_chat_routes.py` — 200 con citas, 422 vacía, 409 activa, **429 por saturación global o espera agotada**, 503 modelo, 504 timeout · Dep: T019 · Check: fallan antes de T061 · Evidence: rojo y verde

### Implementation for User Story 3

- [X] T055 [US3] Implementar recuperación en `src/secguard_advisor/retrieval/search.py` — prefijo de consulta, colección pública + del caso, fusión por score, umbral calibrable, estado `empty` · Dep: T053 · Check: T053 en verde · Evidence: test en verde
- [X] T056 [US3] Implementar citas en `src/secguard_advisor/retrieval/citations.py` — construcción, validación automática, motivos, locator · Dep: T052 · Check: T052 en verde · Evidence: test en verde
- [X] T057 [US3] Implementar el cliente de generación en `src/secguard_advisor/conversation/llm.py` — `ChatOllama` con JSON Schema, `seed`, `temperature`, `num_ctx`, `num_predict`, timeout; sin fallback · Dep: T013 · Check: `tests/unit/test_llm_client.py` · Evidence: test en verde
- [X] T058 [US3] Redactar el prompt v1 en `src/secguard_advisor/conversation/prompts.py` — español, hechos/recomendaciones/insuficiencia, sin cifras inventadas, sin certificar, ignorar instrucciones incrustadas · Dep: T057 · Check: revisión y test de ausencia de secretos · Evidence: prompt `chat-v1`
- [X] T059 [US3] Implementar los dos controles de concurrencia en `src/secguard_advisor/conversation/concurrency.py` — exclusión por caso (índice único) y semáforo global de una generación con espera `SECGUARD_GENERATION_QUEUE_TIMEOUT_SECONDS` (segundos), adquirido antes de crear la ejecución y liberado en `finally` · Dep: T027 · Check: `tests/unit/test_concurrency_guard.py` (mismo caso, dos casos, espera agotada, **desconexión del cliente que no libera ni permite otra generación**, finalización real que libera; los tres eventos se distinguen) · Evidence: test en verde
- [X] T060 [US3] Implementar el grafo base en `src/secguard_advisor/conversation/graph.py` y `nodes.py` — `load_scope → retrieve → agent → validate → (repair) → persist`, `abstain` sin cita ni herramienta, usando el ciclo de vida de T027 · Dep: T055, T056, T057, T058, T027 · Check: `tests/unit/test_graph_routing.py` · Evidence: rutas ejercitadas
- [X] T061 [US3] Implementar rutas y plantillas de conversación en `src/secguard_advisor/web/routes/chat.py` y `templates/chat/` — pregunta, respuesta, citas, **fragmentos recuperados con procedencia**, visor, marca de borrador; `409` por caso activo, `429` por generación global ocupada, `503`/`504`; respuesta, citas, telemetría y cierre en **una sola transacción** · Dep: T054, T059, T060, T027 · Check: T054 en verde · Evidence: test en verde
- [X] T062 [US3] Implementar abstención en `src/secguard_advisor/conversation/nodes.py` — plantilla, `outcome`, distinción entre falta documental y respuesta por herramienta · Dep: T060 · Check: `tests/unit/test_abstention.py` · Evidence: test en verde
- [X] T063 [US3] Implementar reintento de turno en `src/secguard_advisor/conversation/retry.py` y `web/routes/chat.py` — reutiliza la pregunta, crea intento nuevo (`attempt_no`, `retry_of_run_id`), sin mensaje duplicado; solo para `failed`/`timeout`/`interrupted` y **sin respuesta persistida**; distingue pregunta nueva, reintento y envío duplicado; **429 por saturación global o espera agotada**, coherente con T061 · Dep: T061, T027 · Check: `tests/unit/test_turn_retry.py` (los tres casos, rechazo con respuesta y **429 por saturación global o espera agotada**) · Evidence: test en verde
- [X] T064 [US3] Implementar revisión humana del respaldo en `src/secguard_advisor/retrieval/review.py` y `web/routes/review.py` — estados, autor desde `SECGUARD_REVIEWER_NAME`, fecha y observación; rechaza con `409` si la identidad no está configurada; valida `message_id` y `citation_id` dentro del caso; sin P1–P4 ni aprobación de informes · Dep: T056, T061 · Check: `tests/unit/test_citation_review.py` (incluye identidad vacía y recurso ajeno) · Evidence: test en verde
- [X] T065 [US3] Prueba de respuesta real en `tests/integration/test_answer_real.py` — corpus ingerido, cita válida, fragmento localizable · Dep: T061, T046 · Check: `make test-integration` · Evidence: salida con cita y locator
- [X] T066 [US3] Prueba de ausencia de evidencia en `tests/integration/test_no_evidence.py` — abstención, cero citas inventadas · Dep: T062, T046 · Check: `outcome=insufficient_evidence` · Evidence: test en verde
- [X] T067 [US3] Prueba de cita inválida en `tests/integration/test_citation_rejection.py` — fragmento inexistente o paráfrasis; se rechaza y registra · Dep: T056, T061 · Check: cita ausente y motivo registrado · Evidence: test en verde
- [X] T068 [US3] Prueba del flujo de revisión en `tests/integration/test_citation_review_flow.py` — pendiente → respaldada/no respaldada, autor desde configuración, fecha y observación; sin identidad configurada devuelve `409`; mensaje o cita de otro caso devuelve `404`; una cita `valid` sin revisión no se presenta como fundamentada · Dep: T064 · Check: estados visibles y persistidos · Evidence: test en verde

**Evidencia de US3 (2026-11-08)**

- `make check`: 197 pruebas rápidas en verde (6 de integración deseleccionadas); Ruff y formato correctos.
- `make test-integration`: 6 pruebas reales en verde (2 de US2 + 4 de US3) en 78 s.
- Umbral de recuperación calibrado con datos de humo del corpus real: preguntas pertinentes con similitud ≥ 0,58; preguntas fuera de dominio ≤ 0,05. Se fijó `retrieval_min_score = 0.35`; filtra candidatos débiles, no prueba ausencia de evidencia.
- Generador real `qwen3.5:9b` (digest `56671c2ab938…`), `num_ctx=8192`, temperatura 0.1, semilla 42, salida estructurada JSON Schema. Se desactivó el razonamiento del modelo: con razonamiento activo la salida estructurada no llegaba a producirse (400 tokens, 29 s); desactivado responde en 2,7 s.
- T065: pregunta real sobre el corpus ingerido; respuesta `answered` con dos citas válidas del CSF 2.0 (página 8 `p:8#7` y página 31 `p:31#30`), cita literal verificada contra el fragmento persistido y localizador coincidente.
- T066: pregunta fuera de dominio sin documentos; `outcome=insufficient_evidence`, cero citas persistidas y mensaje de abstención.
- T067: paráfrasis sobre un fragmento real recuperado; dos intentos rechazados con motivo `quote_not_found`, `outcome=abstained_invalid_citations`, sin citas válidas.
- T068: flujo completo por rutas: cita `valid` mostrada como «pendiente de revisión» y nunca como respaldada; sin `SECGUARD_REVIEWER_NAME` la revisión devuelve 409 y no escribe; con identidad configurada registra autor, fecha y observación; mensaje de otro caso devuelve 404.
- Servidor real con almacenamiento temporal y corpus real: pregunta 200 en 33 s con «Borrador no revisado», control automático, «pendiente de revisión», fragmentos recuperados y procedencia; cita válida página 8 `p:8#7`; revisión humana 200 «Revisado: respaldada por Revisora Local»; evidencia de ejecución 200; tras reiniciar, el historial y la revisión persisten.
- Contrato: 8 pruebas de rutas del chat (200 con citas, 422 vacía, 409 caso activo, 429 por saturación global, 503 modelo, 504 timeout, procedencia en el panel, evidencia de ejecución y aislamiento 404).
- Concurrencia: exclusión por caso mediante índice único, permiso global de una generación adquirido antes de crear la ejecución, espera acotada, liberación en `finally` y desconexión del cliente que no libera antes del cierre real.
- Revisión visual en navegador: pendiente; no hay navegador disponible.

**Checkpoint**: US3 funcional; flujo documental con evidencia y revisión humana.

### Ajuste de experiencia de usuario (post-US3, 2026-11-08)

**Alcance**: indicador visible de progreso, bloqueo de envíos duplicados y contraste del botón de
revisión. No renumera tareas, no cambia rutas, contratos, concurrencia, reintentos ni persistencia.

**Formularios ajustados**:

- Consulta documental (`chat/panel.html`): «Consultando las fuentes y preparando la respuesta…».
- Carga de documentos (`documents/list.html`): «Enviando y procesando el documento…».
- Reintento de procesamiento (`documents/detail.html`): «Reintentando el procesamiento del documento…».
- Reintento de consulta (`chat/panel.html`): «Reintentando la consulta…».
- Registro de revisión (`chat/_citation.html`): «Guardando revisión…».

**Comportamiento**:

- `static/js/forms.js` (propio, sin dependencias) marca el formulario con `aria-busy="true"`, muestra
  el indicador con `role="status"` y `aria-live="polite"`, y deshabilita el botón de envío.
- Un formulario ocupado ignora nuevos envíos por `submit` en fase de captura: cubre doble clic y
  Enter repetido. El bloqueo visual complementa la exclusión por caso y el permiso global del
  servidor; no los sustituye.
- HTMX descarta por defecto los cuerpos 4xx/5xx. Se habilita el reemplazo solo cuando el cuerpo es
  el fragmento del propio destino (mismo `id` que el objetivo), de modo que 409, 422, 429, 503 y 504
  muestran su motivo sin inyectar páginas completas en un panel.
- Los valores de texto se conservan tras un error. La selección de archivo no puede restaurarse por
  seguridad del navegador; el panel lo indica y pide volver a seleccionarlo.
- `run_timeout` e `invalid_model_output` no tenían mensaje propio y caían en «Ocurrió un error
  interno»; se añadieron mensajes específicos sin cambiar estados HTTP ni rutas.
- La región viva permanece en el DOM y se alternan spinner y texto, para que el anuncio sea fiable.
- `prefers-reduced-motion` detiene la animación del spinner (`motion-reduce:animate-none`).
- El espacio del indicador está reservado (`min-h-6`) para evitar saltos de diseño.

**Contraste de «Registrar revisión»**: la causa observada fue que `app.css` no se había recompilado
tras añadir las plantillas de conversación, por lo que las clases de Tailwind del botón no existían.
Se recompiló el CSS y se fijaron estilos explícitos: `bg-slate-900` con texto blanco (contraste
17,85:1), hover negro (21:1) y estado deshabilitado `bg-slate-400` con `text-slate-900` (6,96:1).

**Evidencia**:

- `tests/contract/test_pending_ui.py`: 7 pruebas en verde (marcado pendiente en consulta, documentos
  y revisión; motivo visible sin `SECGUARD_REVIEWER_NAME`; raíces de fragmento para 422 y 415;
  fragmento de cita en 409; script servido).
- `make check`: 204 pruebas rápidas en verde (6 de integración deseleccionadas); Ruff y formato
  correctos. `make test-integration`: 6 en verde.
- Servidor real con almacenamiento temporal: panel de consulta con `data-form-key`, `role="status"`,
  `aria-live`, mensaje y clases deshabilitadas; panel de documentos con su mensaje; 422 del chat con
  raíz `<section id="chat-panel">`; 415 de documentos con raíz `<section id="documents-panel">`;
  `/static/js/forms.js` servido como `text/javascript`; `app.css` con `disabled:bg-slate-400`.
- `npm run build`: CSS recompilado con las clases nuevas; sin cambios en recursos vendorizados.

**Verificación en navegador (Playwright MCP, Chrome, 2026-11-08)**

Con el servidor real en `127.0.0.1:8800`, almacenamiento del proyecto y demora controlada de 4 s por
intercepción de red en el navegador (sin cambios en producción):

- Caso creado desde la interfaz; paneles de documentos y consulta renderizados.
- Carga de PDF: durante la solicitud el formulario quedó `aria-busy="true"`, con spinner visible
  (16×16, animación `spin`) y el mensaje «Enviando y procesando el documento…», botón deshabilitado;
  al terminar, documento «Disponible».
- Error 415: el panel se reemplazó con el motivo, el título y la versión declarada se conservaron, el
  archivo se reinició con el aviso de volver a seleccionarlo, el botón se rehabilitó y el indicador se
  ocultó.
- Error 409 por contenido duplicado: mismo comportamiento de restauración y mensaje comprensible.
- Consulta con doble clic sobre «Preguntar»: **un solo POST** `/chat/messages`, un solo mensaje de
  pregunta, indicador y botón deshabilitado durante la espera; respuesta con dos citas, «Borrador no
  revisado», control automático y fragmentos recuperados con procedencia.
- Revisión humana: spinner y mensaje «Guardando revisión…», botón deshabilitado, nota y selección
  conservadas; tras el reemplazo, «Respaldo semántico: respaldada por Revisora Visual» y, en la otra
  cita, «no respaldada por Revisora Visual», con fecha y observación.
- Movimiento reducido emulado: la animación del spinner pasa a `none` (0 s).
- Tras recargar la página y tras varios reemplazos HTMX, los indicadores y los formularios siguen
  funcionando y las revisiones persisten.

**Defectos encontrados y corregidos en esta verificación**:

1. El spinner nunca se mostraba: `hidden` es una propiedad de `HTMLElement`, y en un `<svg>`
   (`SVGElement`) `elemento.hidden = false` no elimina el atributo, por lo que
   `[hidden]{display:none}` seguía aplicándose. Ahora se alterna el atributo con
   `setAttribute`/`removeAttribute`.
2. Copia redundante en la cita: «Control automático (existencia y cita literal): Control automático:
   válida» y «Respaldo semántico: Respaldo pendiente de revisión». Se simplificaron las etiquetas.
3. El indicador del formulario de revisión era un cuarto elemento de la fila flexible y podía
   reflotar los controles; ahora se muestra debajo de la fila con el espacio ya reservado.
4. Los errores del servidor no se veían porque HTMX descarta los cuerpos 4xx/5xx; se habilitó el
   reemplazo solo cuando el cuerpo es el fragmento del propio destino.

### Ajuste de navegación y presentación (post-US3, 2026-11-08)

**Alcance**: cabecera, barra lateral de escritorio, menú desplegable móvil, ruta de navegación y
separación de la ficha del caso en secciones GET independientes. No cambia contratos POST, reglas de
concurrencia, persistencia, aislamiento por caso ni el tratamiento de citas.

**Diseño implementado**:

- Cabecera con la marca, la leyenda «Escenario educativo» y botón «Abrir menú» en móvil.
- Barra lateral con «General» (Casos, Nuevo caso) y, dentro de un caso, «Caso abierto» con el nombre
  y las secciones Resumen, Documentos y Consulta documental. El elemento activo usa color, fondo,
  borde y `aria-current="page"`.
- Ruta de navegación (`nav` + `ol` con separadores) y título de sección en el contenido.
- Una sola sección visible por página, con navegación GET y renderizado del servidor. HTMX se
  conserva dentro de cada sección: el panel de documentos y el de consulta siguen siendo fragmentos.
- Móvil: menú cerrado al cargar, apertura con el botón, cierre con botón, Escape, fondo y selección
  de destino; foco al panel al abrir y restauración al control de apertura; trampa de Tab.
- «Fragmentos recuperados» pasa a un bloque `<details>` nativo: sobrevive a los reemplazos HTMX sin
  reinicializar componentes de Flowbite.
- Se usan los componentes gratuitos de Flowbite ya instalados (sidebar, drawer, breadcrumbs, botones,
  formularios, alertas) con Tailwind local; sin CDN ni dependencias nuevas.
- Iconos SVG locales definidos en `components/icon.html`.

**Rutas**:

- Reutilizadas: `/cases`, `/cases/new`, `/cases/{id}/documents`, `/cases/{id}/documents/{doc}`,
  `/cases/{id}/documents/{doc}/versions/{v}/fragments/{chunk}`, `/cases/{id}/chat`,
  `/cases/{id}/runs/{run_id}` y los POST existentes.
- Ajuste de presentación: `GET /cases/{id}` deja de incluir documentos y conversación y pasa a ser
  **Resumen**; `GET /cases/{id}/documents` devuelve la página completa cuando no es HTMX y el panel
  cuando lo es.
- Sin rutas nuevas: cada sección ya tenía una ruta o se sirve desde la existente.

**Evidencia**:

- `tests/contract/test_navigation.py`: 12 pruebas (grupos de la barra, sección activa, secciones
  directas, fragmento sin shell, rutas de navegación, aislamiento, nombre largo, recursos locales,
  fragmento de corpus público y destino de regreso).
- `make check`: 216 pruebas rápidas en verde; `make test-integration`: 6 en verde.
- `npm run build`: CSS recompilado; dos ejecuciones producen el mismo SHA-256
  (`54c515936aba7085f7f1aa9544c0440957b4b50906d14206013c0304eb06c3b6`).
- Playwright MCP (Chrome) con servidor real sobre almacenamiento temporal y corpus ingerido:
  escritorio 1440 × 900, móvil 390 × 844 y 320 px, sin desbordamiento horizontal; secciones activas y
  rutas de navegación verificadas tras recargar; documento cargado y abierto; consulta real con
  Ollama (dos citas del CSF), indicador y un solo POST con doble clic, revisión humana registrada y
  persistente; errores 415 y 409 con panel reemplazado y campos conservados; menú móvil con foco,
  Escape, fondo, cierre al navegar y restauración de foco.
- Consola: sin errores tras añadir el favicon local; las únicas entradas son las respuestas 4xx
  provocadas a propósito y el icono faltante previo, ahora resuelto.
- Capturas en `docs/evidencia/navegacion/`: `escritorio-casos.png`, `escritorio-resumen.png`,
  `escritorio-documentos.png`, `escritorio-documentos-cargando.png`,
  `escritorio-consulta-cargando.png`, `escritorio-consulta.png`, `escritorio-ejecucion.png`,
  `movil-menu.png`, `movil-contenido.png` y `movil-320.png`.

**Defectos encontrados y corregidos en la validación**:

1. Las citas al corpus público abrían un `404`: la ruta de fragmentos solo aceptaba documentos del
   caso. Ahora acepta documentos públicos cuando el alcance del caso está autorizado, sigue
   rechazando documentos de otro caso y muestra el origen.
2. Encabezados duplicados («Documentos» en el título y en el panel) y espaciado del formulario de
   revisión; se ajustaron las plantillas.
3. El foco inicial del menú móvil caía en el fondo superpuesto en lugar del botón de cierre; el panel
   ahora recibe el foco y restaura al control de apertura.

### Ajuste de identidad visual y resaltado (2026-11-08)

- Icono aprobado copiado a `src/secguard_advisor/web/static/icons/` (`secguard-icon.svg`,
  `favicon.ico` y `secguard-icon-512.png`). La cabecera usa el SVG a 28 px en móvil y 32 px en
  escritorio, con `alt=""` y `aria-hidden="true"` porque acompaña al nombre. Se enlazan favicon SVG e
  ICO y `apple-touch-icon`; se retiró el favicon anterior para no dejar referencias contradictorias.
- Resaltado de citas: `find_quote_span` construye la cadena normalizada con un índice hacia cada
  carácter original y devuelve el tramo exacto; el `<mark>` envuelve ese tramo, conservando saltos de
  línea y espacios. Si el tramo no vuelve a normalizarse igual que la cita, no se resalta. La
  validación de citas no cambió y no se usan coincidencias aproximadas.
- A 320 px la insignia «Escenario educativo» se oculta (`min-width: 360px`) para que icono, nombre y
  botón de menú quepan sin desbordar.
- `AGENTS.md`: corregida la frase que presentaba `make corpus` como no implementado.
- Evidencia: `tests/unit/test_quote_highlight.py` (8), `tests/contract/test_navigation.py` (15, con
  icono, recursos y resaltado de extremo a extremo), `make check` 227 en verde y
  `make test-integration` 6 en verde. CSS recompilado y reproducible
  (`b52e4a6b8d32737bcb1dcd7b7b55983dbfa5b0c3dff1056769480b1b8a0cfc74`).
- Playwright: icono cargado y legible en escritorio y móvil; 320, 360 y 390 px sin desbordamiento;
  recursos del icono y favicon con 200, sin peticiones fallidas ni errores de consola; cita real del
  CSF resaltada conservando el salto de línea y caso negativo sin `<mark>`; indicadores de carga y
  navegación sin regresiones.
- Capturas: `docs/evidencia/navegacion/escritorio-identidad.png`, `movil-390-identidad.png`,
  `movil-320-identidad.png` y `cita-resaltada.png`.

---

## Phase 6: User Story 4 - Continuar la conversación (Priority: P2)

**Goal**: memoria persistente por caso, separada entre casos y consistente tras reinicio o fallo.

**Independent Test**: dos turnos dependientes, reinicio, y dos casos sin contaminación cruzada.

### Tests for User Story 4

- [X] T069 [P] [US4] Pruebas de memoria en `tests/unit/test_memory.py` — `thread_id` correcto, reconstrucción desde mensajes, rechazo de checkpoint ajeno · Dep: T019 · Check: fallan antes de T070 · Evidence: rojo y verde

### Implementation for User Story 4

- [X] T070 [US4] Configurar el checkpointer en `src/secguard_advisor/conversation/memory.py` — `storage/checkpoints.sqlite`, `SqliteSaver`, `thread_id = conversation_id`, verificación de identidad · Dep: T069 · Check: T069 en verde · Evidence: test en verde
- [X] T071 [US4] Implementar persistencia de conversación en `src/secguard_advisor/conversation/service.py` — conversación única por caso, `seq`, reutilización de la pregunta en reintentos, reconciliación del checkpoint desde `messages` (recortar si está adelantado, reconstruir si falta), sin prometer atomicidad entre bases · Dep: T070, T027 · Check: `tests/unit/test_conversation_persistence.py` · Evidence: test en verde
- [X] T072 [US4] Integrar memoria en el grafo y el historial visible en `graph.py` y `templates/chat/history.html` · Dep: T071, T060 · Check: `tests/integration/test_memory_followup.py` · Evidence: test en verde
- [X] T073 [US4] Prueba de reinicio y aislamiento en `tests/integration/test_memory_restart_isolation.py` — conversación intacta; dos casos sin fuga · Dep: T072, T018 · Check: historial y contexto separados · Evidence: test en verde
- [X] T074 [US4] Prueba de fallo a mitad de turno en `tests/integration/test_midturn_failure.py` — fallo de la transacción final: sin mensaje asistente ni citas, ejecución `failed` o `interrupted`, reintento permitido; checkpoint adelantado: se recorta desde `messages`; sin duplicados · Dep: T073, T063 · Check: estado consistente y conteo de mensajes · Evidence: test en verde

**Evidencia de US4 (2026-11-08)**

- `tests/unit/test_memory.py` (9): instantánea por conversación, checkpoint ajeno rechazado,
  reconstrucción desde `messages`, exclusión de la pregunta actual, recorte por mensajes y
  caracteres, solo turnos completos, huella del último mensaje y estados `rebuilt_missing`,
  `rebuilt_stale`, `trimmed_ahead` y `rebuilt_foreign`.
- `tests/unit/test_conversation_persistence.py` (6): una conversación por caso, secuencia, pregunta
  persistida, exclusión de la pregunta reintentada, historial sin mensajes de otro caso y consulta de
  recuperación ampliada.
- `tests/integration/test_memory_followup.py`: seguimiento con historial confirmado en el prompt y
  citas nuevas asociadas a la respuesta correcta.
- `tests/integration/test_memory_restart_isolation.py`: reinicio con historial y contexto intactos;
  dos casos con marcas distintivas sin fuga entre prompts, mensajes ni checkpoints.
- `tests/integration/test_midturn_failure.py`: fallo de la transacción final sin mensaje asistente ni
  citas, ejecución `failed`, reintento permitido y sin duplicados; checkpoint adelantado recortado y
  desactualizado reconstruido, verificado en el paso `load_memory`.
- `tests/integration/test_memory_followup_real.py`: con Ollama y CSF 2.0 ingerido, Q1 y Q2
  respondidas con citas; reinicio de motor y memoria; Q3 «¿Cuál de las funciones acabamos de
  profundizar?» responde GOVERN con cita válida.
- `make check`: 243 pruebas rápidas en verde; `make test-integration`: 12 en verde.
- Playwright con servidor real y almacenamiento temporal: doble clic en la primera pregunta produce
  un solo POST con spinner y botón deshabilitado; recarga conserva el historial; reinicio del
  servidor conserva 2 turnos y la tercera pregunta responde GOVERN con 4 citas; el otro caso aparece
  vacío y al volver el historial sigue completo; revisión humana persistente; 0 errores de consola;
  móvil sin desbordamiento.
- Defecto corregido: una cita rechazada sin fragmento resoluble rompía la transacción final por
  clave foránea y devolvía 500; ahora la fila se omite y el motivo queda en el paso `validate`.
- Capturas en `docs/evidencia/us4/`: `carga.png`, `primera-pregunta.png`, `segunda-pregunta.png`,
  `tras-reinicio.png`, `tercera-pregunta.png`, `caso-a-completo.png` y `movil.png`.

### Ajuste del presupuesto de contexto (post-US4, 2026-11-08)

**Causa**: el historial se limitaba por caracteres y la evidencia por `token_count` medido con
EmbeddingGemma. No existía una comprobación del total antes de invocar a Qwen3.5. Un primer cierre usó
`ceil(bytes / 2,4)`, calibrado con pocas muestras; **no era una garantía**: hay entradas con menos
bytes por token y el margen de 320 no estaba demostrado para esa frontera. Esta corrección sustituye
esa estimación por el tokenizador del propio generador.

**Solución**: `conversation/budget.py` mide el prompt completo antes de cada llamada (incluida la
reparación) con `conversation/tokenizer.py`:

- vocabulario y fusiones BPE leídos del GGUF ya instalado por Ollama (`gguf`); sin descargas en
  ejecución ni llamadas pagadas;
- pre-tokenización de bytes con la misma expresión regular que el binario de Ollama y tokens
  especiales registrados (`tokenizers`, ya presente como dependencia transitiva, ahora explícita);
- plantilla de conversación que reproduce el renderizador `Qwen35Renderer` (system + user + turno de
  asistente con bloque de razonamiento vacío), verificada contra `prompt_eval_count`;
- límite `num_ctx - num_predict - 320` = 6672. El margen cubre variaciones de plantilla o versión del
  renderizador, **no** incertidumbre del tokenizador.

**Elementos incluidos**: instrucciones, pregunta, historial, fuentes con título, identificador y
localizador, envoltorio de plantilla, salida reservada (1200) y margen (320).

**Reducción**: sin cambios. Primero el historial más antiguo por turnos completos; después las fuentes
de menor rango, conservando `S1..Sk`. La pregunta y los textos incluidos no se recortan; el historial
persistido no se modifica. Si el mínimo no cabe, `context_budget_exceeded` (500) sin llamar al modelo.
Si el tokenizador no está disponible, `context_budget_unavailable` (503) sin estimar ni llamar.

**Regresión del divisor 2,4**: con 1200 bytes aleatorios en Base64, el diagnóstico por bytes da 1534
tokens y el tokenizador 1753. Con un límite de 1534 el control anterior habría admitido la llamada y
el nuevo la rechaza. En el prompt real, en cambio, el diagnóstico sobrestima (9670 frente a 6074), lo
que confirma que no sirve como cota en ninguna dirección.

**Evidencia**:

- `tests/unit/test_context_budget.py` (11): estimación solo diagnóstica, ajuste completo, historial
  por turnos completos, fuentes deterministas, reparación, pregunta y fuentes íntegras, mínimo que no
  cabe, pregunta gigante, entradas sin mutar y tokenizador no disponible.
- `tests/integration/test_context_budget_pipeline.py` (3): prompt acotado con historial persistido
  intacto, reparación acotada y fallo `context_budget_exceeded` sin llamar al generador.
- `tests/contract/test_chat_routes.py`: 500 con `context_budget_exceeded` y 503 con
  `context_budget_unavailable`, ambos sin invocar al generador.
- `tests/integration/test_context_budget_real.py` (2): admisión 6074, observado 6013, límite 6672,
  reserva 1200, margen 320, 0 turnos y 0 fuentes descartados; y la regresión Base64 (1534 frente a
  1753). La calibración del tokenizador dio 24 = 24 en el prompt mínimo, +1 en español y +17-21 en
  técnico/Base64 (conteo por encima del observado).
- `make check`: 258 en verde; `make test-integration`: 17 en verde (6 min 55 s).

**Checkpoint**: US4 funcional.

---

## Phase 7: User Story 5 - Consultar hallazgos mediante una herramienta (Priority: P2)

**Goal**: herramienta de lectura acotada al caso, conteos recalculables y origen de la invocación visible.

**Independent Test**: preguntar un conteo, recalcularlo de forma independiente y comparar; preguntar por otro caso y comprobar la negativa.

### Tests for User Story 5

- [X] T075 [P] [US5] Pruebas de la herramienta en `tests/unit/test_findings_tool.py` — argumentos, filtros, conteos vs recálculo, límite, caso ajeno, caso sin hallazgos y **ausencia de `case_id` en el resultado** · Dep: T023, T015 · Check: fallan antes de T076 · Evidence: rojo y verde

### Implementation for User Story 5

- [X] T076 [US5] Implementar la herramienta en `src/secguard_advisor/tools/findings.py` — alcance en clausura, esquema sin `case_id`, ORM parametrizado, `COUNT(*)`, resultado sin identificador de caso · Dep: T075 · Check: T075 en verde · Evidence: test en verde
- [X] T077 [US5] Vincular la herramienta al grafo en `conversation/graph.py` — máximo 2 llamadas, `origin=model_requested`, error de argumentos al modelo, traza interna en `run_tool_calls` · Dep: T076, T060 · Check: `tests/unit/test_tool_binding.py` · Evidence: test en verde
- [X] T078 [US5] Prueba de pregunta solo-herramienta en `tests/integration/test_tool_only_question.py` — sin candidatos documentales, la herramienta responde y no se abstiene · Dep: T077 · Check: `outcome=answered` con evidencia estructurada · Evidence: test en verde
- [X] T079 [US5] Prueba de aislamiento y vacío en `tests/integration/test_findings_isolation.py` — caso ajeno sin datos; caso sin hallazgos `total=0` · Dep: T077 · Check: cero filas ajenas · Evidence: test en verde
- [X] T080 [US5] Mostrar resultado de la herramienta y etiqueta sintética en `templates/chat/message.html` · Dep: T077 · Check: aserciones sobre HTML · Evidence: test en verde

**Evidencia de US5 (2026-11-08)**

- `tests/unit/test_findings_tool.py` (21): esquema estricto sin `case_id`, filtros individuales y
  combinados, conteos contrastados con un recálculo independiente en SQLite, CVE múltiple sin
  multiplicar filas, agrupaciones por severidad y activo, límite y `truncated`, valores ausentes sin
  inventar, caso vacío, aislamiento entre dos casos, argumentos inválidos y timeout.
- `tests/unit/test_tool_binding.py` (9): la decisión del modelo ejecuta la herramienta y registra
  `origin=model_requested`, argumentos validados y resumen sin filas; corrección tras error de
  argumentos; rechazo de `case_id`; máximo de dos llamadas; fallos de base y timeout.
- `tests/integration/test_tool_only_question.py`: pregunta respondida solo con la herramienta, cero
  citas documentales y cifras contrastadas.
- `tests/integration/test_findings_isolation.py`: dos casos con activos distintivos sin fuga y caso
  sin hallazgos con total 0.
- `tests/contract/test_findings_ui.py` (5): etiqueta sintética, filtros, totales y grupos, detalle
  limitado, procedencia, aviso de que no es Qualys, estado vacío y error de argumentos; la página de
  ejecución muestra la invocación.
- `tests/integration/test_findings_real.py` (Ollama): el modelo solicitó `findings_query` con
  `severity=High, group_by=asset`; total 4 y grupos `api-gateway 2`, `customer-portal 1`,
  `internal-wiki 1`, idénticos al recálculo en SQLite. Presupuesto del segundo turno: admitido 817,
  observado 802.
- `make check`: 292 en verde; `make test-integration`: 21 en verde (9 min 24 s).
- Playwright con el caso de demostración (`make seed-demo`) en almacenamiento temporal: doble clic
  produce un solo POST con indicador y botón deshabilitado; el bloque muestra «Herramienta consultada:
  findings_query», «Datos educativos sintéticos», «Total: 4», los tres grupos, la procedencia y el
  aviso de que no es una importación de Qualys; recarga y página de ejecución conservan la
  invocación; un caso sin hallazgos muestra «Total: 0», «Sin dataset asociado» y la nota de que no
  demuestra ausencia de vulnerabilidades; móvil 390 sin desbordamiento; 0 errores de consola.
- **Adaptación documentada (R25)**: con `format` (salida estructurada) Ollama no emite `tool_calls`
  nativos, y las reglas de respuesta sesgaban al modelo hacia `missing_info`. La selección se separa
  en una llamada estructurada `ToolDecision` (sin heurísticas por palabra) y una llamada de respuesta
  con el resultado. Se conservan los argumentos estrictos, el máximo de dos llamadas, la corrección
  de errores y el control de presupuesto (también para la decisión y para los resultados).
- Capturas: `docs/evidencia/us5/carga.png`, `herramienta.png`, `vacio.png` y `movil.png`.

---

## Phase 8: User Story 6 - Verificar la ejecución (Priority: P2)

**Goal**: evidencia de ejecución completa, límites, intentos y trazas honestas.

**Independent Test**: ejecutar con y sin LangSmith disponible y comprobar el registro local y el estado de traza en ambos casos.

### Tests for User Story 6

- [ ] T081 [P] [US6] Pruebas de la evidencia de ejecución en `tests/unit/test_run_states.py` — transiciones persistidas, `attempt_no`, una activa por caso, `confirmed` nunca escrito por la aplicación y serialización de pasos, fuentes y herramientas · Dep: T027 · Check: fallan antes de T082 · Evidence: rojo y verde

### Implementation for User Story 6

- [ ] T082 [US6] Implementar las consultas de evidencia en `src/secguard_advisor/evidence/runs.py` — lectura y serialización de pasos, fuentes, herramientas e intentos, con `origin` determinista o del modelo; la escritura y el cierre ya viven en T027 · Dep: T027, T081 · Check: T081 en verde · Evidence: test en verde
- [ ] T083 [US6] Implementar trazas en `src/secguard_advisor/evidence/tracing.py` — envoltura, metadatos, `flush`, `trace_status` (`disabled`/`submitted`/`failed`), nunca `confirmed` · Dep: T013 · Check: `tests/unit/test_tracing_status.py` · Evidence: test en verde
- [ ] T084 [US6] Implementar límites y errores en `conversation/graph.py` — 8 pasos, 2 herramientas, 1 reparación, 120 s de turno, 90 s por llamada; mapeo a `model_unavailable`, `model_timeout`, `step_limit`, `tool_call_limit` · Dep: T060, T027 · Check: `tests/unit/test_limits.py` · Evidence: test en verde
- [ ] T085 [US6] Implementar ruta y plantilla de evidencia en `src/secguard_advisor/web/routes/runs.py` y `templates/runs/` — modelo, duración, estado, fuentes, herramientas, intentos, error, traza y **ambos controles de cita** (automático y revisión humana) · Dep: T082, T083 · Check: `tests/contract/test_runs_routes.py` · Evidence: test en verde
- [ ] T086 [US6] Prueba de integración de traza y caída en `tests/integration/test_trace_and_fallback.py` — traza `submitted`; LangSmith no disponible; consulta local completa · Dep: T083, T085 · Check: ejecución con y sin credenciales · Evidence: salida de ambos escenarios
- [ ] T087 [US6] Prueba de secretos en `tests/unit/test_no_secrets.py` — ni clave ni rutas absolutas en respuestas, registros ni plantillas · Dep: T085 · Check: test en verde · Evidence: test en verde

**Checkpoint**: US6 funcional; las seis historias quedan cubiertas.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: interfaz integrada, recorrido de aceptación, integración real, documentación y evidencia.

- [ ] T088 Consolidar la navegación y el layout integrado — el shell (cabecera, barra lateral, menú móvil, rutas de navegación y secciones GET) ya está implementado en el «Ajuste de navegación y presentación»; queda integrar las secciones de US4–US6 cuando existan, revisar estados vacíos y errores de esas historias y ejecutar la revisión visual integrada · Dep: T033, T048, T061, T080, T085 · Check: prueba de navegación y ausencia de duplicación de plantillas · Evidence: shell en verde en `tests/contract/test_navigation.py`; integración pendiente de US4–US6
- [ ] T089 Escribir la suite de aceptación en `tests/acceptance/test_journey.py` — recorrido con dobles rápidos: caso, documentos, pregunta, seguimiento, hallazgos, abstención, reinicio, dos casos, pregunta nueva, reintento, envío duplicado, generación global ocupada y revisión · Dep: T088 · Check: `make test` · Evidence: recorrido en verde sin Ollama
- [ ] T090 Ejecutar el recorrido real en `tests/acceptance/test_journey_real.py` — Ollama, embeddings, recuperación y herramienta; registrar resultados observados · Dep: T089, T046 · Check: `make test-integration` · Evidence: reporte con fecha y salidas reales
- [ ] T091 Confirmar la traza observada con `scripts/confirm_trace.py` — responsabilidad de la persona que ejecuta la aceptación; recibe `run_id` y `trace_id`, verifica por API de lectura que la traza existe en `secguard-advisor-dev` y solo entonces registra `confirmed`; registra su identidad, la fecha y la evidencia (salida del comando e identificador) · Dep: T086, T090 · Check: el script rechaza una traza inexistente y no confirma solo por invocar el SDK · Evidence: salida del comando, identidad y fecha en el reporte de aceptación
- [ ] T092 Validar `quickstart.md` de punta a punta y corregir divergencias · Dep: T090 · Check: cada paso produce el resultado descrito · Evidence: notas por paso
- [ ] T093 Verificar coherencia documental y de gobierno — README («Implementado»/«Previsto»), `AGENTS.md`, arquitectura y registro de decisiones de `CONSTITUTION.md`; **verificar**, no concentrar actualizaciones: cada commit significativo ya actualizó lo suyo · Dep: T088 · Check: revisión de que cada cambio tiene su actualización en el mismo commit · Evidence: lista de commits y documentos
- [ ] T094 Ejecutar `make check` y `make test-integration` y registrar el resultado real · Dep: T093 · Check: salida completa sin ocultar fallos · Evidence: salida con fecha
- [ ] T095 Preparar el paquete de evidencia de la demo — recorrido, citas, revisiones, ejecuciones, traza y límites declarados · Dep: T091, T092, T094 · Check: cada afirmación tiene evidencia · Evidence: `docs/evidencia/demo-001.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Fase 1 (Setup)**: sin dependencias. T001 primero; el resto según sus `Dep`.
- **Fase 2 (Foundational)**: depende de Fase 1. **Bloquea todas las historias.**
- **Fase 3 (US1)**: depende de Fase 2.
- **Fase 4 (US2)**: depende de US1 y de Fase 2.
- **Fase 5 (US3)**: depende de US2 (fragmentos indexados) y de T027/T059.
- **Fase 6 (US4)**: depende de US3 (grafo y rutas).
- **Fase 7 (US5)**: depende de US3. Comparte `conversation/graph.py`, por lo que **no** es paralela
  con US4.
- **Fase 8 (US6)**: depende de US3 y US5.
- **Fase 9 (Polish)**: depende de todas las historias.

### Critical path

`T001 → T013..T027 → T030..T033 → T039..T049 → T055..T065 → T070..T074 → T076..T080 → T082..T086 → T088..T095`

El camino crítico pasa por la ingesta real (T045–T049) y la respuesta citada (T055–T065): son los
puntos donde un fallo de diseño obliga a rehacer trabajo posterior.

### Parallel opportunities

- Fase 1: T002, T003, T004 y T006 en paralelo tras T001. Luego T005, T007, T008, T009 y T010.
  T011 espera a T010; T012 espera a T002 y T004.
- Fase 2: tras T013 va T014; tras T014, T015 y T022; tras T015, T016, T023 y T027; tras T016,
  T017 y T018; tras T019, T020 y T021. T025 depende de T009; T026 de T006.
- US2: T034–T038 en paralelo. T039–T042 en paralelo tras sus pruebas; T043 tras T042; T044 tras
  T039–T043; T045 tras T039 y T040; T046 tras T044 y T045.
- US3: T052–T054 en paralelo.
- **No paralelizar US4 y US5**: ambas modifican `conversation/graph.py`.
- Fase 8: T081 primero; T082 y T083 en paralelo; T084–T085 después.

---

## Implementation Strategy

### MVP mínimo verificable

1. Fases 1 y 2 completas.
2. US1 (caso) y US2 (documentos) con ingesta real.
3. US3 (consulta con citas y revisión humana).
4. Detenerse y validar el recorrido documental.

El MVP **no** acepta el incremento: H4, H5 y H6 son obligatorias para la aceptación completa.

### Entrega incremental

1. Fundación → US1 → US2 → US3: flujo documental con evidencia.
2. US4: memoria.
3. US5: herramienta.
4. US6: evidencia, intentos y trazas.
5. Polish: interfaz integrada, aceptación real y documentación.

### Gobierno de commits

Cada commit que cambie arquitectura, tecnología o proceso **actualiza la constitución y el registro
de decisiones en el mismo commit**. T093 solo verifica que eso ocurrió; no concentra las
actualizaciones.

---

## Notes

- [P] solo cuando los archivos son distintos y no hay dependencia pendiente.
- Exclusión por caso (índice único) y semáforo global de generación son controles distintos: uno
  protege el caso, el otro protege la máquina. No se sustituyen entre sí.
- Respuesta, citas, telemetría y cierre de ejecución comparten una transacción; ninguna transacción
  queda abierta durante la inferencia.
- `SECGUARD_REVIEWER_NAME` es una identidad local declarada, no autenticación. Sin valor no se
  guarda ninguna revisión.
- Ninguna prueba de `data/eval/final/` se usa para calibrar el umbral ni para elegir configuración.
- Un conteo agregado de Ollama nunca se presenta como validación individual de todos los fragmentos.
- El estado `confirmed` de traza solo lo escribe `scripts/confirm_trace.py` tras verificar la traza
  en LangSmith.
- No se declaran resultados, métricas ni estados de CI antes de ejecutarlos.
- Los originales del corpus viven fuera de Git; el manifiesto es la fuente de procedencia.
