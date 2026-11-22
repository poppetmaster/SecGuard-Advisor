# Tasks: Migración del índice documental a Qdrant

**Input**: Documentos de diseño de `/specs/004-qdrant-vector-index/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md y
checklists/requirements.md

**Tests**: incluidas porque la constitución aplica test-first cuando existe una prueba determinista y
un resultado esperado claro.

**Estado**: planificación corregida tras el análisis de consistencia documental. Ninguna tarea está
ejecutada ni marcada como completada. No se instalan dependencias, no se levantan servicios, no se
ejecutan migraciones, no se reconstruyen índices ni se modifican datos.

## Formato

Cada tarea usa:

```text
- [ ] TNNN [P?] [US?] Descripción con archivo o comando concreto
  - Story: Setup|Foundational|US1..US7|Polish
  - Dep: dependencias explícitas o none
  - Verifies: tarea de implementación que evalúa (solo pruebas y verificaciones)
  - Check: comprobación observable
  - Evidence: archivo, diff, salida o reporte requerido
```

`[P]` significa que la tarea puede ejecutarse en paralelo con otra tarea de la misma fase porque sus
dependencias ya están completas y no comparte archivos editables con ella. No significa que no tenga
dependencias ni que pueda adelantarse a ellas.

Las tareas de prueba se escriben antes de la implementación que evalúan y `Verifies` identifica esa
implementación. Las verificaciones finales no crean comportamiento nuevo. Las descripciones están en
español; los identificadores, rutas y nombres de código se conservan en inglés.

## Path Conventions

- Código: `src/secguard_advisor/`
- Pruebas: `tests/unit/`, `tests/contract/`, `tests/integration/`, `tests/acceptance/`
- Scripts: `scripts/`
- Infraestructura: `compose.qdrant.yml`, `Makefile`, `.env.example`
- Control de la aplicación: `<SECGUARD_STORAGE_DIR>/qdrant-control/` (marcadores, locks, reportes)
- Volumen del servidor: `./storage/qdrant` (solo archivos de Qdrant)
- Documentación: `README.md`, `AGENTS.md`, `docs/`, `specs/004-qdrant-vector-index/`,
  `.specify/memory/constitution.md`

---

## Fase 1: Setup (Corte 1 — fundación Qdrant y namespace)

**Objetivo**: Qdrant local, configuración de instancia, namespace y lock listos para integrar, sin
cambiar todavía el backend de la aplicación.

- [x] T001 Añadir `qdrant-client==1.20.0` a `pyproject.toml` y actualizar `uv.lock`; conservar las dependencias de Chroma hasta T072.
  - Story: Setup
  - Dep: none
  - Check: `uv lock --check` y `uv sync --locked` resuelven; `grep qdrant-client pyproject.toml` devuelve la versión fijada.
  - Evidence: diff de `pyproject.toml` y `uv.lock`, salida de los comandos.

- [x] T002 [P] Crear `compose.qdrant.yml` con `qdrant/qdrant:v1.20.0`, puertos loopback `127.0.0.1:6333` y `127.0.0.1:6334`, volumen persistente `./storage/qdrant` y política de reinicio.
  - Story: Setup
  - Dep: none
  - Check: `docker compose -f compose.qdrant.yml config` valida; imagen, puertos y volumen coinciden con el plan.
  - Evidence: compose y salida de `config`.

- [x] T003 [P] Añadir `SECGUARD_INSTANCE_ID`, `SECGUARD_QDRANT_URL` y `SECGUARD_QDRANT_TIMEOUT_SECONDS` a `src/secguard_advisor/config.py`; validar el slug de instancia; conservar `chroma_dir` de forma temporal.
  - Story: Setup
  - Dep: none
  - Check: las pruebas de configuración cubren ID ausente/inválido y URL válida; el resto de la suite sigue pasando.
  - Evidence: diff de configuración y salida de pruebas unitarias.

- [x] T004 Actualizar `.env.example` con instancia, URL de Qdrant, timeout y la nota de que los IDs son estables y únicos por almacenamiento.
  - Story: Setup
  - Dep: T003
  - Check: las variables están presentes, sin credenciales ni rutas privadas.
  - Evidence: diff de `.env.example`.

- [x] T005 [P] Añadir `qdrant-up`, `qdrant-down` y `qdrant-health` al `Makefile`, cada uno con comentario `##` para que aparezca en `make help`; no añadir `qdrant-rebuild` todavía.
  - Story: Setup
  - Dep: T002, T003
  - Check: `make -n qdrant-up qdrant-down qdrant-health` muestra comandos reproducibles; `make help` lista los tres.
  - Evidence: diff del `Makefile` y salida de `make help`.

- [x] T006 [P] Añadir pruebas unitarias en rojo de instancia en `tests/unit/test_qdrant_instance.py`: validación de slug, marcador y fingerprint por ruta canónica, composición de namespace, reglas de registro, lock de archivo, registro de propietario (operación e intento) y sondeo de solo lectura (`inspect`) que no crea ni modifica archivos; un registro residual con el lock libre no demuestra actividad.
  - Story: Setup
  - Dep: T003
  - Verifies: T007
  - Check: fallan porque `retrieval/instance.py` no existe todavía.
  - Evidence: salida RED.

- [x] T007 Implementar `src/secguard_advisor/retrieval/instance.py` como único responsable de la primitiva: validación de slug, composición de namespace, marcador con fingerprint (SHA-256 de la ruta canónica del almacenamiento combinada con `instance_id`, sin hashear contenido), reglas de registro sin adopción silenciosa, lock de archivo exclusivo con registro de propietario (operación e intento) escrito solo mientras se posee el lock, y sondeo de solo lectura (`inspect`) que no crea, trunca ni modifica archivos.
  - Story: Setup
  - Dep: T006
  - Check: T006 pasa; el fingerprint no cambia al escribir archivos ni el marcador; el registro de propietario solo se considera válido mientras el lock está tomado por un proceso vivo; no se crea tabla ni migración.
  - Evidence: módulo, salida GREEN, ausencia de diff en `alembic/`.

- [x] T008 Pruebas de contrato de despliegue en `tests/contract/test_qdrant_deployment.py`: compose fijado, puertos loopback, volumen persistente, `.env.example`, namespace de instancia y presencia de los targets en `make help`.
  - Story: Setup
  - Dep: T002, T003, T004, T005
  - Verifies: T002, T003, T004, T005
  - Check: las pruebas pasan y aseguran que Chroma sigue declarado en esta fase.
  - Evidence: salida de pruebas.

- [x] T009 Verificar disponibilidad de la imagen en arm64 y salud local con `docker manifest inspect qdrant/qdrant:v1.20.0`, `make qdrant-up` y `curl -fsS http://127.0.0.1:6333/readyz`; verificar además los fallos de ID y namespace.
  - Story: Setup
  - Dep: T002, T005, T006, T007
  - Verifies: T002, T005, T007
  - Check: el manifiesto reporta la imagen; `/readyz` responde 200; ID ausente/inválido y namespace incompatible fallan con mensaje claro.
  - Evidence: salida de comandos, respuesta de salud y salida de error; el servicio no queda corriendo como parte de la tarea.

**Checkpoint Corte 1**: dependencia fijada, Compose válido, namespace/marcador/lock implementados y
probados, contrato de despliegue verde y disponibilidad arm64/salud verificada. Todavía no cambia el
backend de la aplicación.

---

## Fase 2: Foundational (adaptador, errores y corpus)

**Objetivo**: adaptador Qdrant, taxonomía de errores y ingesta del corpus público listos para las
historias.

- [x] T010 [P] Añadir pruebas unitarias en rojo del adaptador en `tests/unit/test_qdrant_index.py`: UUIDv5 determinista, mapeo de payload, semántica de score y errores clasificados.
  - Story: Foundational
  - Dep: T007
  - Verifies: T013
  - Check: fallan antes de `QdrantIndex`.
  - Evidence: salida RED.

- [x] T011 [P] Añadir pruebas de contrato en rojo de colecciones y alias en `tests/contract/test_qdrant_index_contract.py`: aislamiento por alcance, resolución de alias, nombres con namespace de instancia y payload sin texto.
  - Story: Foundational
  - Dep: T007
  - Verifies: T012, T013
  - Check: fallan antes de las colecciones y del adaptador.
  - Evidence: salida RED.

- [x] T012 Implementar `src/secguard_advisor/retrieval/collections.py` con nombres físicos, alias y generaciones que incluyan el namespace de instancia, usando la primitiva de T007.
  - Story: Foundational
  - Dep: T007
  - Check: las pruebas cubren público/caso, alias, separación de instancias y nombres inválidos.
  - Evidence: módulo y salida de pruebas.

- [x] T013 Implementar `QdrantIndex` en `src/secguard_advisor/retrieval/index.py` con `upsert`, `delete_ids`, `delete_version`, `count`, `query` y errores clasificados.
  - Story: Foundational
  - Dep: T010, T011, T012
  - Check: T010 y T011 pasan; no se guarda texto en el payload; no hay fallback a Chroma.
  - Evidence: módulo y salida GREEN.

- [x] T014 Actualizar `src/secguard_advisor/web/app.py` para construir Qdrant desde la configuración, resolver la instancia y exponer errores de readiness y de configuración.
  - Story: Foundational
  - Dep: T012, T013
  - Check: la fábrica usa Qdrant; un ID de instancia o una URL ausentes fallan con un mensaje claro.
  - Evidence: diff de la fábrica y salida de pruebas.

- [x] T015 Pruebas de contrato de la fábrica, readiness y errores de configuración en `tests/contract/test_qdrant_app.py`.
  - Story: Foundational
  - Dep: T014
  - Verifies: T014
  - Check: pasan sin levantar un servidor Qdrant real.
  - Evidence: salida de pruebas.

- [x] T016 [P] Añadir pruebas unitarias en rojo de la taxonomía de errores en `tests/unit/test_error_messages.py`: los seis códigos conservan su propio código y estado (503/409), presentan mensaje en español y nunca se resuelven como `internal_error`.
  - Story: Foundational
  - Dep: none
  - Verifies: T017
  - Check: fallan mientras los códigos no estén registrados.
  - Evidence: salida RED.

- [x] T017 Registrar en `src/secguard_advisor/web/errors.py` los códigos `qdrant_unavailable` (503), `case_index_unavailable` (503), `public_index_unavailable` (503), `instance_namespace_mismatch` (503), `reconstruction_in_progress` (409) e `ingestion_in_progress` (409), con mensaje comprensible.
  - Story: Foundational
  - Dep: T016
  - Check: T016 pasa; `AppError("case_index_unavailable").code` devuelve `case_index_unavailable` y no `internal_error`.
  - Evidence: diff de `web/errors.py` y salida GREEN.

- [x] T018 Añadir prueba de integración en rojo de la ingesta del corpus público en Qdrant en `tests/integration/test_qdrant_corpus_ingest.py`.
  - Story: Foundational
  - Dep: T013
  - Verifies: T019
  - Check: falla porque la ingesta sigue usando Chroma.
  - Evidence: salida RED.

- [x] T019 Migrar `scripts/ingest_corpus.py` y `scripts/prepare_demo.py` a Qdrant, integrando la adquisición y liberación del lock de instancia con la operación `ingestion`, sin tocar `storage/chroma` ni la instancia del usuario.
  - Story: Foundational
  - Dep: T018
  - Check: la ingesta de prueba crea puntos en el alcance público con procedencia, sin registros Qualys y sin rutas de Chroma; el lock se toma antes de escribir y se libera en `finally`; con el lock tomado por una reconstrucción, la ingesta falla con `reconstruction_in_progress`.
  - Evidence: diff de los scripts y salida GREEN.

- [x] T020 Actualizar los targets `corpus-ingest` y `demo-prepare` del `Makefile` con comentarios `##` y añadir la prueba de contrato que verifica que usan Qdrant y ninguna ruta de Chroma.
  - Story: Foundational
  - Dep: T019
  - Verifies: T019
  - Check: el contrato pasa; `make -n corpus-ingest demo-prepare` no invoca Chroma; `make help` lista los targets.
  - Evidence: diff del `Makefile`, salida del contrato y de `make help`.

**Checkpoint Fase 2**: adaptador, colecciones, fábrica, taxonomía de errores e ingesta del corpus
público en Qdrant verdes. El corpus público puede prepararse y probarse con Qdrant antes de declarar
recuperación pública.

---

## Fase 3: User Story 1 — Reconstruir el índice (P1) 🎯 MVP

**Objetivo**: reconstrucción limpia desde SQLite, con generación/alias, reporte y estados
observables.

**Independent Test**: indexar un caso ficticio desde SQLite, verificar IDs, conteos, payload y alias;
repetir sin duplicados.

- [x] T021 [P] [US1] Añadir prueba de integración en rojo de la reconstrucción inicial desde SQLite en `tests/integration/test_qdrant_rebuild.py`.
  - Story: US1
  - Dep: T012, T013
  - Verifies: T022, T025
  - Check: falla antes de que exista el comando de reconstrucción.
  - Evidence: salida RED.

- [x] T022 [US1] Implementar el núcleo de `scripts/rebuild_qdrant.py`: adquirir el lock de instancia con la operación `rebuild` y liberarlo en `finally`, leer SQLite, seleccionar versiones vigentes disponibles, regenerar embeddings locales y crear una colección de generación.
  - Story: US1
  - Dep: T021
  - Check: T021 avanza hasta la generación esperada sin usar Chroma; el lock se toma antes de leer o escribir y se libera incluso si la reconstrucción falla; con una ingesta activa, el comando falla con `ingestion_in_progress`.
  - Evidence: script y salida RED-to-progress.

- [x] T023 [P] [US1] Añadir pruebas unitarias en rojo del resolvedor único de estado en `tests/unit/test_qdrant_state.py`: `not_started` sin estado, `ingestion_in_progress`, `rebuild_in_progress`, `completed`, `partial`, `failed`, metadatos residuales con el lock libre ignorados, reporte terminal ilegible como error explícito con `state: null` y `last_terminal: null` (nunca `not_started` ni estado inventado) y ausencia de escrituras.
  - Story: US1
  - Dep: T022
  - Verifies: T024
  - Check: fallan antes de `retrieval/status.py`; el caso ilegible no borra, sobrescribe ni repara el reporte.
  - Evidence: salida RED y comparación de archivos del directorio de control.

- [x] T024 [US1] Implementar `src/secguard_advisor/retrieval/status.py` como resolvedor único: `resolve_operation_state(...)` (sondeo del lock, lectura del propietario e interpretación del reporte terminal), `terminal_status(...)` para el estado global del reporte y errores tipados `instance_configuration_invalid`, `lock_unreadable` y `status_report_unreadable`, sin escrituras ni efectos.
  - Story: US1
  - Dep: T023
  - Check: las pruebas de T023 pasan; no existe otra implementación del sondeo, del propietario ni de la interpretación del reporte; un reporte ilegible devuelve error con `last_terminal: null`.
  - Evidence: módulo y salida GREEN.

- [x] T025 [US1] Implementar la validación de UUID, conteos y payload, el cambio de alias, la retención de la generación anterior y el reporte JSON con el estado terminal por alcance y global (`completed`, `partial` o `failed`); los cinco estados de reconstrucción los expone el resolvedor. El estado global del reporte se obtiene del resolvedor único `retrieval/status.py` (`terminal_status`); no se reimplementan el sondeo del lock, la lectura del propietario ni la interpretación del reporte terminal.
  - Story: US1
  - Dep: T022, T024
  - Check: T021 pasa; una validación parcial no cambia el alias; un lock con operación `rebuild` no se reporta como éxito; una ingesta activa no se reporta como reconstrucción en curso; un registro residual con el lock libre no demuestra actividad; la ausencia de reporte no se reporta como fallo.
  - Evidence: salida GREEN y reporte JSON.

- [x] T026 [P] [US1] Añadir pruebas en rojo de la consulta de estado de solo lectura en `tests/integration/test_qdrant_status.py`: `not_started` sin estado registrado, ingesta en curso, reconstrucción en curso, último resultado terminal `completed`, `partial` o `failed`, metadatos obsoletos sin lock activo ignorados, reporte terminal ilegible, configuración de instancia ausente o inválida y archivo de lock existente pero ilegible o lock tomado con registro de propietario ausente o corrupto (en los tres, salida 2, mensaje en `stderr`, JSON con `state: null`, `last_terminal: null` y `error` explícito, sin reparación) y ausencia de efectos de escritura (sin marcador de instancia, colecciones, embeddings, archivos nuevos ni cambio de alias).
  - Story: US1
  - Dep: T024, T025
  - Verifies: T027
  - Check: fallan antes de `--status`; el caso sin estado devuelve `not_started` con salida 0 y no crea archivos; el caso ilegible no se presenta como `not_started` ni como estado terminal y no modifica el reporte.
  - Evidence: salida RED, salida JSON de error y listado de archivos antes y después.

- [x] T027 [US1] Implementar `uv run python scripts/rebuild_qdrant.py --status` como adaptador de la CLI sobre el resolvedor único `retrieval/status.py`: consulta de solo lectura que devuelve `not_started`, `ingestion_in_progress`, `rebuild_in_progress`, `completed`, `partial` o `failed`, sin iniciar reconstrucciones, generar embeddings, crear colecciones, registrar instancias, escribir archivos ni cambiar alias; si el reporte terminal es ilegible, la configuración de instancia falta o es inválida, o el archivo de lock existe pero no puede leerse, finaliza con salida 2, mensaje comprensible en `stderr` y JSON con `state: null`, `last_terminal: null` y `error` explícito (`status_report_unreadable`, `instance_configuration_invalid`, `lock_unreadable`), sin devolver `not_started`, sin afirmar que no existe una operación activa, sin crear marcador, lock, directorios ni otros archivos y sin borrar, sobrescribir ni reparar información.
  - Story: US1
  - Dep: T024, T026
  - Check: las pruebas de T026 pasan; con lock libre y metadatos residuales devuelve el último resultado terminal o `not_started`; con ausencia total de estado devuelve `not_started` y salida 0; reporte ilegible, configuración inválida y lock ilegible devuelven salida 2 con su `error.code` sin inventar estado; el directorio de control queda idéntico (sin marcador, lock ni directorios nuevos).
  - Evidence: salida GREEN, JSON de estado, JSON de error y comparación de archivos.

- [x] T028 [US1] Añadir pruebas de integración en rojo de interrupción, reconstrucción parcial, reintento seguro, ingesta activa y metadatos obsoletos del lock en `tests/integration/test_qdrant_rebuild_failures.py`.
  - Story: US1
  - Dep: T022
  - Verifies: T029
  - Check: fallan antes del manejo de fallos y de la resolución de estado por propietario.
  - Evidence: salida RED.

- [x] T029 [US1] Implementar el reporte de interrupción y parcial, la conservación del alias y la limpieza segura del reintento.
  - Story: US1
  - Dep: T028
  - Check: T028 pasa; una generación parcial nunca queda activa.
  - Evidence: salida GREEN y reporte.

- [x] T030 [P] [US1] Añadir pruebas en rojo de fragmentos no indexables (sin texto, metadatos inválidos, dimensión o modelo incompatible) y de puntos huérfanos sin `chunk_id` en SQLite.
  - Story: US1
  - Dep: T022
  - Verifies: T031
  - Check: fallan antes del reporte de discrepancias.
  - Evidence: salida RED.

- [x] T031 [US1] Implementar la exclusión y el reporte de fragmentos no indexables y el conteo de puntos huérfanos como `extra_chunks`, sin resolverlos como cita.
  - Story: US1
  - Dep: T030
  - Check: T030 pasa; un punto huérfano se reporta y no se devuelve como resultado.
  - Evidence: salida GREEN y reporte.

- [x] T032 [US1] Añadir el target `qdrant-rebuild` al `Makefile`, con comentario `##` para `make help`, usando la configuración de instancia y almacenamiento.
  - Story: US1
  - Dep: T022
  - Check: `make -n qdrant-rebuild` usa el script y ninguna ruta de Chroma; `make help` lo lista.
  - Evidence: diff del `Makefile` y salida de `make -n`.

- [x] T033 [US1] Verificar idempotencia, parcial, reintento, reporte, consulta de estado y ausencia de efectos de escritura con `uv run pytest tests/integration/test_qdrant_rebuild.py tests/integration/test_qdrant_rebuild_failures.py tests/integration/test_qdrant_status.py`.
  - Story: US1
  - Dep: T024, T025, T027, T029, T031
  - Verifies: T022, T024, T025, T027, T029, T031
  - Check: una segunda reconstrucción no duplica; el estado parcial o fallido es explícito; `--status` distingue los seis valores y los errores de reporte, configuración y lock sin escribir; el alias anterior se conserva.
  - Evidence: salida de integración, reporte y comparación de archivos del directorio de control.

**Checkpoint Fase 3**: Qdrant se reconstruye desde SQLite, se valida, reporta estados honestos y permite consultarlos con `--status` sin efectos de escritura.

---

## Fase 4: User Story 2 — Consultar documentos (P1)

**Objetivo**: consultas sobre Qdrant con corpus público, caso actual, citas y fallo de índice
explícito.

**Independent Test**: consultar dos casos ficticios y el corpus público; verificar resultados,
procedencia, ausencia de cruces y que un fallo de índice no produce abstención.

- [x] T034 [P] [US2] Añadir prueba de integración en rojo de recuperación público/caso y resolución de citas en `tests/integration/test_qdrant_retrieval.py`.
  - Story: US2
  - Dep: T012, T013
  - Verifies: T035, T036, T037
  - Check: falla antes de la integración de búsqueda.
  - Evidence: salida RED.

- [x] T035 [US2] Adaptar `src/secguard_advisor/retrieval/search.py`: resolución de alias, similitud coseno, umbral calibrado y errores clasificados de índice.
  - Story: US2
  - Dep: T034
  - Check: T034 usa resultados de Qdrant y no asume `1 - distance`; un fallo de índice eleva un error clasificado.
  - Evidence: diff y salida de pruebas.

- [x] T036 [US2] Adaptar `src/secguard_advisor/documents/service.py` al adaptador Qdrant sin cambiar el protocolo de dominio, integrando la adquisición y liberación del lock de instancia con la operación `ingestion` alrededor de la escritura del índice.
  - Story: US2
  - Dep: T035
  - Check: la ingesta y la recuperación de integración pasan con Qdrant; el lock se toma solo para escribir el índice y se libera en `finally`; con una reconstrucción activa, la ingesta falla con `reconstruction_in_progress`.
  - Evidence: diff y salida de pruebas.

- [x] T037 [P] [US2] Añadir pruebas de contrato en rojo del mapeo de errores en rutas en `tests/contract/test_qdrant_routes.py`: cada código conserva su código y estado, con mensaje comprensible y sin degradarse a `internal_error`.
  - Story: US2
  - Dep: T017, T035
  - Verifies: T038
  - Check: fallan antes de adaptar la fábrica y las rutas.
  - Evidence: salida RED.

- [x] T038 [US2] Adaptar `src/secguard_advisor/web/app.py` y las rutas afectadas: readiness de Qdrant, resultados vacíos y errores clasificados que conservan su código.
  - Story: US2
  - Dep: T036, T037
  - Check: T037 pasa; las rutas devuelven 503/409 con el código correcto para Qdrant no disponible y no declaran «sin evidencia» ante un fallo de índice.
  - Evidence: diff de rutas y salida GREEN.

- [x] T039 [US2] Verificar recuperación público/caso, aislamiento y errores de ruta con `uv run pytest tests/integration/test_qdrant_retrieval.py tests/contract/test_qdrant_routes.py`.
  - Story: US2
  - Dep: T035, T036, T037, T038
  - Verifies: T035, T036, T038
  - Check: el corpus público y el caso actual se recuperan; los documentos privados no cruzan casos; los códigos de error se conservan.
  - Evidence: salida de integración y contrato.

- [x] T040 [P] [US2] Añadir pruebas en rojo de la integración del turno ante fallo de índice en `tests/integration/test_qdrant_index_failure_turn.py`: Qdrant caído, alias público ausente y alias privado esperado ausente; el turno no produce abstención, no ejecuta la generación y registra paso y ejecución con el código.
  - Story: US2
  - Dep: T035, T038
  - Verifies: T041
  - Check: fallan antes de la propagación del fallo.
  - Evidence: salida RED.

- [x] T041 [US2] Implementar la propagación del fallo de índice: `retrieval/search.py` eleva el error clasificado, `conversation/nodes.py` registra el paso con su estado real, y `conversation/graph.py` y `conversation/turn.py` detienen la respuesta y registran la ejecución.
  - Story: US2
  - Dep: T040
  - Check: T040 pasa; el nodo de generación no se ejecuta; la evidencia conserva el código clasificado.
  - Evidence: diff de los cuatro módulos y salida GREEN.

- [x] T042 [US2] Verificar que un fallo de índice nunca produce abstención ni generación documental con `uv run pytest tests/integration/test_qdrant_index_failure_turn.py`.
  - Story: US2
  - Dep: T041
  - Verifies: T041
  - Check: los tres escenarios devuelven su error y no una respuesta de ausencia de evidencia.
  - Evidence: salida de integración.

**Checkpoint Corte 2**: Qdrant atiende consultas de caso y corpus público con ingesta propia, escritores
documentales coordinados por el lock, reconstrucción validada y fallo de índice explícito. El MVP
documental es Corte 1 + Corte 2.

---

## Fase 5: User Story 3 — Citas, procedencia y aislamiento (P2)

**Objetivo**: conservar versiones, citas históricas y evidencia del índice sin reimplementar la lógica
existente.

- [x] T043 [P] [US3] Añadir pruebas de regresión en rojo de versiones superadas, citas históricas y aislamiento entre casos en `tests/integration/test_qdrant_citations.py`, preservando el comportamiento de 001/002.
  - Story: US3
  - Dep: T035, T036
  - Verifies: T044
  - Check: fallan antes de la adaptación, no por comportamiento ausente.
  - Evidence: salida RED.

- [x] T044 [US3] Adaptar la selección de versión vigente en `src/secguard_advisor/retrieval/search.py` preservando el filtro existente; las citas históricas siguen resolviéndose desde SQLite y `retrieval/citations.py` no se reimplementa.
  - Story: US3
  - Dep: T043
  - Check: T043 pasa; el control automático de citas conserva existencia, versión, localizador y cita literal.
  - Evidence: salida GREEN y diff mínimo.

- [x] T045 [P] [US3] Añadir pruebas de contrato en rojo de los campos de evidencia del paso `retrieve` en `tests/contract/test_qdrant_evidence.py` (instancia, backend, versión, modelo, dimensión, alias, generación y `error_code`).
  - Story: US3
  - Dep: T035
  - Verifies: T046
  - Check: fallan antes de los campos de evidencia.
  - Evidence: salida RED.

- [x] T046 [US3] Implementar en `src/secguard_advisor/conversation/nodes.py` los campos de evidencia y el `error_code` clasificado, sin tablas nuevas ni rutas o secretos.
  - Story: US3
  - Dep: T045
  - Check: T045 pasa; la página de ejecución sigue mostrando la evidencia existente.
  - Evidence: diff y salida de pruebas.

- [x] T047 [US3] Verificar citas, versiones, aislamiento y evidencia con `uv run pytest tests/integration/test_qdrant_citations.py tests/contract/test_qdrant_evidence.py`.
  - Story: US3
  - Dep: T044, T046
  - Verifies: T044, T046
  - Check: pasan todas; ninguna cita histórica depende de Qdrant; la evidencia identifica el índice y el código de error cuando falla.
  - Evidence: salida de pruebas.

- [x] T048 [P] [US3] Actualizar `tests/integration/test_qualys_not_rag.py` para contar puntos Qdrant y verificar que ningún registro Qualys entra en el índice documental; ejecutar la regresión de 002.
  - Story: US3
  - Dep: T044
  - Check: cero registros Qualys en las colecciones pública y de caso; la regresión de 002 pasa.
  - Evidence: salida de pruebas y conteos.

---

## Fase 6: User Story 4 — Reiniciar y recuperar disponibilidad (P2)

**Objetivo**: persistencia tras reinicio y errores explícitos sin fallback.

- [x] T049 [P] [US4] Añadir prueba de integración en rojo del reinicio de Qdrant con volumen persistente en `tests/integration/test_qdrant_restart.py`.
  - Story: US4
  - Dep: T012, T014
  - Verifies: T050
  - Check: falla antes del manejo de readiness y persistencia.
  - Evidence: salida RED.

- [x] T050 [US4] Implementar readiness de arranque, validación de instancia y fallo explícito de Qdrant en `src/secguard_advisor/web/app.py`.
  - Story: US4
  - Dep: T049
  - Check: T049 pasa; no hay fallback a Chroma.
  - Evidence: salida GREEN.

- [x] T051 [P] [US4] Añadir pruebas de integración en rojo de Qdrant caído y configuración incompatible en `tests/integration/test_qdrant_availability.py`.
  - Story: US4
  - Dep: T014, T049
  - Verifies: T052
  - Check: fallan antes del mapeo de errores.
  - Evidence: salida RED.

- [x] T052 [US4] Implementar los errores explícitos de disponibilidad y configuración, sin fallback, en `retrieval/index.py` y `web/app.py`.
  - Story: US4
  - Dep: T051
  - Check: T051 pasa; los mensajes son accionables y conservan su código.
  - Evidence: salida GREEN y evidencia de ruta.

- [x] T053 [US4] Verificar reinicio y disponibilidad con `uv run pytest tests/integration/test_qdrant_restart.py tests/integration/test_qdrant_availability.py`.
  - Story: US4
  - Dep: T050, T052
  - Verifies: T050, T052
  - Check: el reinicio conserva el índice; caída y configuración incompatible producen errores clasificados.
  - Evidence: salida de integración.

---

## Fase 7: User Story 6 — Primer documento y alcance vacío (P2)

**Objetivo**: alta incremental sin reconstrucción manual, distinción entre vacío e índice ausente y
recuperación sin atomicidad.

**Independent Test**: cargar el primer documento de un caso sin índice y consultarlo; consultar un
caso sin documentos privados; provocar un fallo de commit en SQLite después de publicar el alias.

- [x] T054 [P] [US6] Añadir pruebas unitarias en rojo del ciclo del primer documento en `tests/unit/test_qdrant_first_document.py`, incluido el fallo de commit en SQLite posterior a la escritura de puntos o a la publicación del alias.
  - Story: US6
  - Dep: T012, T013
  - Verifies: T055
  - Check: fallan antes del manejo del primer documento.
  - Evidence: salida RED.

- [x] T055 [US6] Implementar en `src/secguard_advisor/documents/service.py` la generación y publicación del alias del primer documento, el fallo y reintento, y la convergencia sin atomicidad: SQLite decide la disponibilidad y el reintento no duplica.
  - Story: US6
  - Dep: T054
  - Check: T054 pasa; una versión fallida nunca resuelve; no se exige reconstrucción manual por caso; el reintento converge tras un commit fallido.
  - Evidence: salida GREEN.

- [x] T056 [P] [US6] Añadir pruebas de contrato en rojo de alcance vacío frente a índice ausente en `tests/contract/test_qdrant_scope_errors.py`.
  - Story: US6
  - Dep: T035
  - Verifies: T057
  - Check: fallan antes de la distinción de errores.
  - Evidence: salida RED.

- [x] T057 [US6] Implementar en `src/secguard_advisor/retrieval/search.py` el cálculo del alcance esperado desde SQLite y los errores clasificados de índice.
  - Story: US6
  - Dep: T056
  - Check: T056 pasa; alcance vacío consulta el público y un alias ausente con datos esperados devuelve error.
  - Evidence: salida GREEN.

- [x] T058 [P] [US6] Añadir la prueba de integración del primer documento, alcance vacío y ventana de fallo entre Qdrant y SQLite en `tests/integration/test_qdrant_first_document.py`, sobre la implementación de T055/T057.
  - Story: US6
  - Dep: T055, T057
  - Verifies: T055, T057
  - Check: el primer documento publica alias solo tras validar; un caso vacío consulta el público; es verificación de integración, no prueba RED, porque T055/T057 ya implementan el comportamiento.
  - Evidence: salida de integración.

- [x] T059 [US6] Verificar primer documento, alcance vacío y recuperación convergente con `uv run pytest` sobre las tres suites de la historia.
  - Story: US6
  - Dep: T055, T057, T058
  - Verifies: T055, T057
  - Check: sin reconstrucción manual por caso; el fallo no publica alias nuevo; un índice ausente no se presenta como «sin evidencia».
  - Evidence: salida de pruebas.

---

## Fase 8: User Story 5 — Fallos y recuperación de Qdrant (P3)

**Objetivo**: recuperar el índice sin volver a Chroma.

**Independent Test**: interrumpir una reconstrucción, verificar que el alias anterior se conserva y
que el reintento deja el alcance válido.

- [x] T060 [P] [US5] Añadir prueba de integración en rojo de recuperación tras reconstrucción fallida o parcial en `tests/integration/test_qdrant_recovery.py`.
  - Story: US5
  - Dep: T029
  - Verifies: T061
  - Check: falla antes del manejo de recuperación.
  - Evidence: salida RED.

- [x] T061 [US5] Implementar recuperación, limpieza y reintento de generaciones fallidas en `scripts/rebuild_qdrant.py`, conservando el alias anterior.
  - Story: US5
  - Dep: T060
  - Check: T060 pasa; el alias anterior permanece hasta que exista una generación válida.
  - Evidence: salida GREEN y reporte.

- [x] T062 [P] [US5] Añadir pruebas en rojo de estado por alcance y no finalización global en `tests/integration/test_qdrant_partial_scopes.py`.
  - Story: US5
  - Dep: T029
  - Verifies: T063
  - Check: fallan antes del reporte por alcance.
  - Evidence: salida RED.

- [x] T063 [US5] Implementar el estado por alcance y la semántica global parcial o fallida en `scripts/rebuild_qdrant.py`.
  - Story: US5
  - Dep: T062
  - Check: T062 pasa; un alcance fallido impide un reporte global `completed` sin impedir el alias del alcance validado.
  - Evidence: salida GREEN y reporte JSON.

- [x] T064 [US5] Verificar recuperación y alcances parciales con `uv run pytest tests/integration/test_qdrant_recovery.py tests/integration/test_qdrant_partial_scopes.py`.
  - Story: US5
  - Dep: T061, T063
  - Verifies: T061, T063
  - Check: una reconstrucción fallida no cambia alias; el reintento tiene éxito; el reporte es honesto.
  - Evidence: salida de integración.

---

## Fase 9: User Story 7 — Instancias y concurrencia (P3)

**Objetivo**: aislar instancias y coordinar procesos, reutilizando el namespace y el lock ya
implementados en T007/T012.

- [x] T065 [P] [US7] Añadir prueba de integración en rojo de dos instancias con el mismo `case_id` y documentos distintos en `tests/integration/test_qdrant_instances.py`.
  - Story: US7
  - Dep: T013, T022
  - Verifies: T068
  - Check: falla antes de la verificación de aislamiento.
  - Evidence: salida RED.

- [x] T066 [P] [US7] Añadir la prueba de integración entre dos procesos reales en `tests/integration/test_qdrant_lock_processes.py` sobre los escritores ya integrados: rechazo mutuo entre ingesta y reconstrucción, liberación tras terminar el proceso, terminación abrupta (SIGKILL) y registro de propietario obsoleto tras la muerte.
  - Story: US7
  - Dep: T019, T022, T036
  - Verifies: T019, T022, T036
  - Check: la prueba pasa con los escritores ya integrados; tras matar uno, el lock se libera, el registro residual se ignora y el alias no cambia; es verificación de integración, no prueba RED, porque el uso del lock ya existe en T019/T022/T036.
  - Evidence: salida de integración, registros de proceso y contenido del registro de propietario.

- [x] T067 [US7] Verificar la integración residual del lock en los tres escritores (`scripts/ingest_corpus.py`, `scripts/rebuild_qdrant.py`, `documents/service.py`): confirmar operación e intento, liberación en `finally` y ausencia de duplicación de la primitiva; corregir solo una omisión de integración.
  - Story: US7
  - Dep: T019, T022, T036, T066
  - Verifies: T007, T019, T022, T036
  - Check: T066 pasa; ningún escritor escribe el índice sin el lock; el registro de propietario solo cuenta mientras el lock está tomado por un proceso vivo; no se reimplementa la primitiva.
  - Evidence: salida GREEN, diff de integración y registros de proceso.

- [x] T068 [US7] Verificar aislamiento de instancias, namespace incompatible y lock con `uv run pytest tests/integration/test_qdrant_instances.py tests/integration/test_qdrant_lock_processes.py`.
  - Story: US7
  - Dep: T065, T067
  - Verifies: T065, T067
  - Check: dos instancias con el mismo caso no comparten contenido; el namespace incompatible falla cerrado; una copia del almacenamiento en otra ruta falla cerrado; el lock rechaza y se libera.
  - Evidence: salida de integración.

- [x] T069 [US7] Verificar que no se introdujo tabla ni migración para namespace o lock con `git diff --stat -- alembic/` y `uv run pytest tests/integration/test_case_persistence.py`.
  - Story: US7
  - Dep: T065, T067
  - Verifies: T065, T067
  - Check: sin revisión de Alembic; sólo marcadores, locks y reportes en `qdrant-control/`.
  - Evidence: diff de Alembic y salida de pruebas.

---

## Fase 10: Polish — retiro de Chroma, calibración y cierre

**Objetivo**: retirar Chroma como una sola unidad de trabajo, calibrar, evaluar y cerrar
documentación y constitución.

**Nota de unidad de trabajo**: T070–T073 forman una sola unidad. T071 adapta las pruebas y T072 retira
el código; no se declara verde ni se integra hasta T073. No se conservan dos backends operativos para
evitar ese trabajo.

- [ ] T070 [P] Añadir pruebas en rojo que exigen ausencia de imports y dependencias ejecutables de Chroma en `tests/unit/test_qdrant_no_chroma.py`.
  - Story: Polish
  - Dep: T012, T013
  - Verifies: T072
  - Check: fallan mientras Chroma siga importado o declarado.
  - Evidence: salida RED.

- [ ] T071 Adaptar fixtures y pruebas que instancian Chroma a Qdrant (unitarias, contrato, integración y aceptación), sin declarar verde todavía.
  - Story: Polish
  - Dep: T037, T059
  - Check: las pruebas adaptadas pasan con Qdrant; la suite completa puede seguir fallando por el código de Chroma pendiente de retiro.
  - Evidence: diff de fixtures y pruebas, salida por suite.

- [ ] T072 Retirar `ChromaIndex`, `chroma_dir`, la fábrica y las dependencias `langchain-chroma`/`chromadb` del código de producto y de `pyproject.toml`, y actualizar `.specify/memory/constitution.md` en el mismo commit registrando «backend sustituido; aceptación pendiente».
  - Story: Polish
  - Dep: T070, T071
  - Check: T070 pasa; la constitución registra «backend sustituido; aceptación pendiente» y no declara «implementado» ni «aceptado»; `CONSTITUTION.md` sigue siendo el enlace simbólico a `.specify/memory/constitution.md` y no hay copia duplicada.
  - Evidence: diffs, salida GREEN de T070 y diff de la constitución.

- [ ] T073 Verificar el retiro con `make check`, ausencia de imports ejecutables de Chroma y archivos de datos de Chroma intactos.
  - Story: Polish
  - Dep: T072
  - Verifies: T070, T072
  - Check: `make check` verde; `grep` no encuentra imports ejecutables de Chroma; `storage/chroma` existe sin cambios.
  - Evidence: salida de comandos y listado del sistema de archivos.

- [ ] T074 [P] Añadir prueba o guion en rojo de la calibración del umbral en `tests/integration/test_qdrant_threshold.py`.
  - Story: Polish
  - Dep: T035
  - Verifies: T075
  - Check: falla antes de la implementación de calibración.
  - Evidence: salida RED.

- [ ] T075 Implementar `scripts/calibrate_qdrant_threshold.py` con valores propuesto y observado separados, criterios fijados antes de evaluar y sin copiar 0.35.
  - Story: Polish
  - Dep: T074
  - Check: T074 pasa; calibración y evaluación final usan conjuntos distintos; el reporte distingue propuesto de observado.
  - Evidence: salida GREEN y reporte de calibración.

- [ ] T076 Aplicar el umbral calibrado en `src/secguard_advisor/config.py` y su documentación, sin conservar 0.35 como predeterminado validado.
  - Story: Polish
  - Dep: T075
  - Check: el valor aplicado proviene de la calibración y queda documentado; ninguna prueba depende del 0.35 de Chroma.
  - Evidence: diff de configuración y salida de pruebas.

- [ ] T077 [P] Añadir el conjunto de evaluación funcional en `tests/fixtures/qdrant_eval.py` y `tests/integration/test_qdrant_functional_eval.py`, separado de la calibración, con corpus público, dos casos ficticios y fuentes esperadas.
  - Story: Polish
  - Dep: T035, T075
  - Verifies: T078
  - Check: los datos de evaluación son distintos de los de calibración y no contienen datos privados ni Qualys.
  - Evidence: archivos de fixture y prueba.

- [ ] T078 Ejecutar y reportar la evaluación funcional contra Qdrant con el umbral calibrado ya aplicado y congelado en `config.py`, y con un conjunto distinto del usado en la calibración.
  - Story: Polish
  - Dep: T076, T077
  - Check: la evaluación usa el valor aplicado en T076 y no recalibra; el conjunto es distinto del de calibración; cubre corpus público, documentos del caso, aislamiento, versiones, citas históricas y ausencia de Qualys; no ajusta criterios para aprobar.
  - Evidence: salida de evaluación con el umbral aplicado registrado.

- [ ] T079 Aceptación ASGI de los flujos afectados en `tests/acceptance/test_qdrant_ui.py` y verificación real con Playwright MCP registrada en `docs/evidencia/`; no se añaden dependencias de navegador automatizado.
  - Story: Polish
  - Dep: T037, T071, T078
  - Verifies: T037, T071
  - Check: los flujos de documentos, vulnerabilidades y chat renderizan en ASGI; la verificación real con Playwright MCP se registra con comandos y resultado observado.
  - Evidence: salida de pruebas y registro en `docs/evidencia/`.

- [ ] T080 Actualizar `README.md`, `AGENTS.md`, `docs/` y los documentos de `specs/004-qdrant-vector-index/`; documentar el papel limitado del modo embebido y la interfaz operativa de reconstrucción (comando, reporte y consulta `--status`).
  - Story: Polish
  - Dep: T072, T073, T078, T079
  - Check: ningún documento vigente presenta Chroma como backend activo; el modo embebido se describe como recurso de pruebas; las referencias históricas quedan etiquetadas.
  - Evidence: diffs de documentación y verificación de enlaces.

- [ ] T081 Ejecutar la regresión de 001 y 002 más la suite completa de integración y aceptación con Qdrant mediante `make check` y `make test-integration`.
  - Story: Polish
  - Dep: T080
  - Verifies: T072, T075, T076, T078, T079, T080
  - Check: ambas puertas pasan; Qualys permanece sólo en SQLite; no hay fallback a Chroma.
  - Evidence: salida de comandos y reporte de pruebas.

- [ ] T082 Registrar la evidencia de aceptación final y actualizar `.specify/memory/constitution.md` en el mismo commit con «implementado y aceptado localmente», únicamente con la evidencia observada de T081: sin pérdida de datos, Chroma intacto y ninguna capacidad declarada antes de observarla.
  - Story: Polish
  - Dep: T081, T076
  - Verifies: T072, T075, T076, T078, T079, T080, T081
  - Check: los datos del usuario no cambian; el directorio de Chroma permanece; la evidencia enlaza comandos y resultados; la constitución pasa a «implementado y aceptado localmente» solo después de T081 y conserva el enlace simbólico sin copia.
  - Evidence: reporte de aceptación final y evidencia de sistema de archivos y diff.

---

## Dependencias y orden de ejecución

### Cortes

- **Corte 1 (T001–T009)**: fundación independiente. Todas sus dependencias están dentro del corte.
- **Corte 2 (T010–T042)**: depende del Corte 1. Entrega adaptador, taxonomía de errores, ingesta del
  corpus público con lock, reconstrucción con lock y estados, consulta y fallo de índice explícito.
  Es el MVP documental junto con el Corte 1. Ningún escritor de este corte queda operativo sin la
  coordinación del lock.
- **Corte 3 (T043–T053)**: depende del Corte 2. Entrega citas/evidencia y reinicio/disponibilidad.
- **Corte 4 (T054–T064)**: depende del Corte 2. Entrega primer documento y alcance vacío (US6, P2) y
  recuperación/parciales (US5, P3), en ese orden para respetar la prioridad de la especificación.
- **Corte 5 (T065–T069)**: depende del Corte 2, que integra los escritores; la primitiva del lock
  proviene del Corte 1. Entrega la
  prueba entre procesos del lock (incluida terminación abrupta) y la verificación residual de su
  integración en los escritores; no reimplementa la primitiva ni el uso.
- **Corte 6 (T070–T082)**: depende de todos los anteriores. Retira Chroma, calibra, evalúa con el
  umbral aplicado, actualiza la constitución y cierra.

### Ruta crítica

```text
T001 → T002/T003 → T005/T006 → T007 → T010/T011 → T012 → T013 → T014
→ T018/T020/T021/T034 → T019/T022/T026/T035 → T023/T024/T025/T027
→ T033/T037/T040 → T038 → T041 → T042
→ T044/T050/T055 → T047/T053/T059 → T066 → T067 → T068
→ T070/T071 → T072 → T073 → T074 → T075 → T076 → T077 → T078
→ T079 → T080 → T081 → T082
```

Ninguna dependencia apunta a una tarea de un corte posterior. Las pruebas se escriben antes de la
implementación que verifican; `Verifies` no es una dependencia de planificación.

### Oportunidades de paralelismo

Cada par comparte corte, tiene sus dependencias completas y no comparte archivos editables:

- T002 ∥ T003.
- T005 ∥ T006 (Makefile frente a pruebas de instancia).
- T010 ∥ T011, y ambas ∥ T016 (adaptador frente a taxonomía de errores).
- T018 ∥ T021 ∥ T034 (ingesta de corpus, reconstrucción y recuperación usan archivos distintos).
- T026 ∥ T030 (estado de solo lectura frente a fallos de reconstrucción).
- T036 ∥ T037 (servicio de documentos frente a contrato de rutas).
- T040 ∥ T043 (fallo de turno frente a regresión de citas).
- T043 ∥ T045 ∥ T049.
- T048 ∥ T049 (regresión Qualys frente a reinicio, archivos distintos).
- T050 ∥ T051 (readiness en `app.py` frente a pruebas de disponibilidad).
- T054 ∥ T056.
- T058 ∥ T060.
- T060 ∥ T062.
- T065 ∥ T066.
- T070 ∥ T074.

Secuenciales por archivo compartido: T022 → T025 → T027 → T029 → T031 (mismo script de
reconstrucción); T034 → T035 → T036; T037 → T038 (prueba antes de implementación); T043 → T044;
T045 → T046; T049 → T050 → T052; T054 → T055; T056 → T057; T060 → T061; T062 → T063;
T066 → T067 → T068; T070 → T071 → T072 → T073; T074 → T075 → T076 → T077 → T078; T079 → T080 →
T081 → T082. T072, T080 y T082 se ejecutan en secuencia porque comparten documentación normativa
(estado intermedio y estado final de la constitución).

---

## Mapa de cobertura

### Requisitos funcionales

| FR | Implementación | Comprobación |
|---|---|---|
| FR-001 | T022, T069 | T069, T082 |
| FR-002 | T022, T025 | T033, T082 |
| FR-003 | T022, T025 | T021, T033 |
| FR-004 | T071, T081 | T048, T081 |
| FR-005 | — (sin ruta de indexación) | T048 |
| FR-006 | T013, T081 | T048, T081 |
| FR-007 | T080, T082 | T082 |
| FR-008 | T022 | T021 |
| FR-009 | T022, T025 | T021 |
| FR-010 | T025 | T033 |
| FR-011 | T024, T025, T027 | T023, T026, T033 |
| FR-012 | T029 | T028 |
| FR-013 | T029 | T028 |
| FR-014 | T031 | T030 |
| FR-015 | T031 | T030 |
| FR-016 | T022 | T033, T070 |
| FR-017 | — (reconstrucción de solo lectura) | T069, T082 |
| FR-018 | T035, T036 | T034, T039 |
| FR-019 | T035 | T034, T039 |
| FR-020 | T044 | T043, T047 |
| FR-021 | T044 | T043, T047 |
| FR-022 | T044 | T043, T047 |
| FR-023 | T044, T046 | T047 |
| FR-024 | T057 | T056, T047 |
| FR-025 | T077, T078 | T078 |
| FR-026 | T074, T075, T076 | T074, T075, T076 |
| FR-027 | T075 | T075 |
| FR-028 | T002, T005 | T008, T009 |
| FR-029 | — (decisión de alcance) | T080 |
| FR-030 | T017, T038 | T016, T037, T051 |
| FR-031 | T052, T072 | T051, T070 |
| FR-032 | T050 | T049, T053 |
| FR-033 | T052 | T051 |
| FR-034 | T046 | T045 |
| FR-035 | T070, T072 | T073 |
| FR-036 | T046 | T045 |
| FR-037 | T025, T029, T063 | T033, T062, T064 |
| FR-038 | — (restricción negativa) | T070, T080 |
| FR-039 | T061 | T060, T064 |
| FR-040 | — (restricción negativa) | T072, T073, T082 |
| FR-041 | T077 | T077, T081 |
| FR-042 | T077 | T081, T082 |
| FR-043 | T077, T081 | T081, T082 |
| FR-044 | T022, T082 | T069, T082 |
| FR-045 | — (restricción negativa) | T081, T082 |
| FR-046 | T024, T025, T027, T038 | T023, T026, T033, T079 |
| FR-047 | T046 | T045 |
| FR-048 | T080 | T080, T082 |
| FR-049 | T071, T079 | T079, T081 |
| FR-050 | — (restricción negativa) | T080 |
| FR-051 | T003, T007, T012 | T006, T008, T068 |
| FR-052 | T007 | T006, T009, T068 |
| FR-053 | T055 | T054, T058 |
| FR-054 | T055 | T054, T058 |
| FR-055 | T041, T057, T052 | T040, T042, T056 |
| FR-056 | T019, T022, T036 | T066, T067 |
| FR-057 | T012, T065 | T065, T068 |
| FR-058 | T007, T012 | T069 |
| FR-059 | T007, T024, T025, T027 | T006, T023, T026, T028, T066 |

Los FR marcados con «—» son restricciones negativas o decisiones de alcance: se verifican por
inspección o regresión y no requieren una tarea de implementación propia.

Tareas de soporte sin un FR único, verificadas por las tareas que habilitan: T001 (fijación de la
dependencia), T004 (`.env.example`), T010/T011 y T015 (contratos previos de adaptador y fábrica),
T014 (fábrica de aplicación, habilitante de FR-030 y FR-032), T018 y T020 (ingesta del corpus público
en Qdrant y contrato de sus targets; la implementación es T019, mapeada en FR-056) y T032 (target de
reconstrucción, habilitante de FR-008).

### Criterios de éxito

| SC | Tareas | SC | Tareas |
|---|---|---|---|
| SC-001 | T021, T033 | SC-013 | T074, T075, T076 |
| SC-002 | T033 | SC-014 | T081 |
| SC-003 | T028, T029, T033 | SC-015 | T045, T046 |
| SC-004 | T043, T047 | SC-016 | T070, T072, T073 |
| SC-005 | T034, T039 | SC-017 | T077, T081, T082 |
| SC-006 | T034, T039 | SC-018 | T073, T082 |
| SC-007 | T043, T044, T047 | SC-019 | T080, T082 |
| SC-008 | T048 | SC-020 | T065, T068 |
| SC-009 | T040, T042 | SC-021 | T054, T058 |
| SC-010 | T049, T053 | SC-022 | T056, T040, T041 |
| SC-011 | T051, T053 | SC-023 | T066, T067, T068 |
| SC-012 | T077, T078 | SC-024 | T009, T065, T068 |

### Historias

| Historia | Fase | Tareas |
|---|---|---|
| US1 (P1) | 3 | T021–T033 |
| US2 (P1) | 4 | T034–T042 |
| US3 (P2) | 5 | T043–T048 |
| US4 (P2) | 6 | T049–T053 |
| US6 (P2) | 7 | T054–T059 |
| US5 (P3) | 8 | T060–T064 |
| US7 (P3) | 9 | T065–T069 |

---

## Primer corte recomendado y condiciones de cierre

**Recomendado: Corte 1 — T001–T009.**

Resultado verificable: dependencia fijada, Compose con Qdrant 1.20.0 en loopback y volumen,
`SECGUARD_INSTANCE_ID` validado, marcador con fingerprint por ruta canónica, namespace y lock
probados, contrato de despliegue verde y disponibilidad arm64/salud verificada en ejecución.

**Condiciones de cierre:**

1. `uv lock --check` y `uv sync --locked` resuelven con `qdrant-client==1.20.0`.
2. `docker compose -f compose.qdrant.yml config` es válido; imagen, puertos y volumen coinciden.
3. Pasan las pruebas de instancia, marcador, fingerprint, namespace y lock, y el contrato de
   despliegue.
4. `SECGUARD_INSTANCE_ID` ausente o inválido, namespace incompatible y marcador ausente con namespace
   existente fallan de forma explícita.
5. `make qdrant-up` + `/readyz` funciona en arm64; el servicio no queda corriendo como parte de la
   verificación.
6. No se modificó SQLite, no se creó una tabla y no se borraron archivos de Chroma.

Después del Corte 1, el Corte 2 puede comenzar. El MVP funcional es Corte 1 + Corte 2.

---

## Contradicciones o decisiones realmente pendientes

- No constan los acuerdos de Cristian Quebrada y Ruben Dario Sabogal; no se inventan ni se solicitan
  de nuevo. La ratificación del responsable está registrada.
- La disponibilidad y el rendimiento de la imagen Qdrant para arm64 se verifican en T009; no se
  declaran probados.
- La semántica exacta del lock por sistema operativo se implementa en T007, se integra en los
  escritores iniciales (T019, T022, T036) y se prueba con dos procesos y terminación abrupta en
  T066/T067.
- La calibración del umbral y la separación calibración/evaluación final se cierran en T074–T078; no
  se copia 0.35, el valor aplicado se registra en `config.py` (T076) y la evaluación final (T078) usa
  ese valor congelado y un conjunto distinto.
- El lock identifica operación e intento mediante un registro asociado al bloqueo real; un registro
  residual con el lock libre se ignora (FR-059).
- Un fallo de un alcance deja el reporte global `partial`; los alcances validados pueden tener su
  propio alias. No se declara una reconstrucción global completa.
- `SECGUARD_INSTANCE_ID` debe configurarse en cada entorno; no hay valor generado por arranque.
- Orden de fases dentro del Corte 4: US6 (P2) antes de US5 (P3); los IDs se asignaron en ese orden.
- FR-029 (modo embebido reservado a pruebas o alternativa documentada) no recibe tarea propia: se
  documenta en T080 y en research.md D-19; no se habilita como alternativa de producción.
- FR-046 se resolvió como interfaz operativa de comando y reporte; no se añade pantalla web de
  administración en 004.
- No se ejecutaron pruebas, servicios, instalaciones ni reconstrucciones en este paso.

## Notas

- `[P]` significa paralelismo real: dependencias completas y archivos distintos. No elimina
  dependencias ni autoriza adelantar tareas.
- Las pruebas se escriben antes de la implementación que verifican; `Verifies` identifica esa tarea.
- No se crean tablas SQLite para el índice, la instancia o el lock.
- La autoridad de actividad del lock es el bloqueo real: el registro de propietario solo cuenta
  mientras un proceso vivo lo posee.
- El volumen del servidor (`./storage/qdrant`) y el control de la aplicación (`qdrant-control/`) son
  rutas distintas.
- Los datos de prueba son públicos o ficticios; el CSV privado de Qualys no se usa para el RAG.
- Cada corte deja un resultado verificable y no puede declarar terminado un índice parcial.
- No se marca ninguna tarea como completada en este documento.
