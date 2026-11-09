---
description: "Tareas de implementación para importación de vulnerabilidades Qualys"
---

# Tasks: Importación de vulnerabilidades Qualys y findings_query

**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md),
[checklists/requirements.md](./checklists/requirements.md)

**Prerequisites**: plan, spec, research, modelo de datos y contratos vigentes.

**Tests**: se incluyen tareas de prueba en cada corte; las pruebas se escriben antes de la
implementación correspondiente.

**Política de importación**: `staged` solo si todo el archivo es válido; `rejected` ante cualquier
error bloqueante; no existe aceptación parcial ni snapshot parcial; solo `confirmed` es consultable.

## Format: `[ID] [P?] [Story] Descripción`

- **[P]**: archivo distinto, dependencias completas y sin conflicto de archivos.
- **[Story]**: US1, US2 o US3 cuando la tarea pertenece a una historia.
- Cada tarea incluye ruta, dependencia, comprobación y evidencia.

## Phase 1: Setup

- [ ] T001 Crear o cambiar a la rama `002-qualys-findings-import` desde el estado actual, conservando los commits documentales; no hacer reset, rebase ni reescritura — Dep: ninguna · Check: `git branch --show-current` y `git log --oneline -3` · Evidence: rama y hashes observados, sin cambios de historia
- [ ] T002 Crear el esqueleto del módulo y los parámetros de límites/políticas en `src/secguard_advisor/vulnerabilities/__init__.py` y `src/secguard_advisor/config.py` — límites 10 MiB, 10.000 filas, 20.000 caracteres por campo, 1.000 CVE; versiones `qualys-csv-1`, `project-severity-1-5-v1`, `qualys-status-v1`, `qualys-evidence-both-v1` · Dep: T001 · Check: import del módulo y valores por defecto en una prueba rápida · Evidence: salida de import y valores observados
- [ ] T003 [P] Registrar en `.specify/memory/constitution.md`, `AGENTS.md` y `README.md` la decisión de instantáneas independientes, rechazo único y sección «Vulnerabilidades» — Dep: T001 · Check: documentos sin contradicción con `spec.md` y `plan.md` · Evidence: diff documental y registro de decisión

## Phase 2: Foundational (bloquea las historias)

**Propósito**: esquema, políticas, parser, validación y staging compartidos. Ninguna historia puede
cerrarse sin estos componentes.

- [ ] T004 [P] Crear fixtures sintéticos representativos en `tests/fixtures/files/qualys_synthetic_valid.csv`, `qualys_synthetic_second.csv`, `qualys_synthetic_mixed.csv`, `qualys_synthetic_invalid_header.csv`, `qualys_synthetic_invalid_rows.csv` y `tests/fixtures/qualys.py` — BOM, comas, comillas, multilínea, cuatro estados, desconocido, severidades 1–5, múltiples CVE, ambos/solo uno/vacío/negativo/indeterminado; sin datos reales · Dep: T002 · Check: cada fixture se parsea con el lector de prueba y sus conteos esperados quedan declarados · Evidence: archivos y conteos sintéticos
- [ ] T005 [P] Escribir pruebas de políticas en `tests/unit/test_qualys_policies.py` — severidad 1 Informativa a 5 Crítica, estados admitidos/desconocidos, grupos de estado, evaluación de `Exploitability` y `Associated Malware`, prioridad conjunta, versiones · Dep: T004 · Check: las pruebas fallan antes de T009 · Evidence: rojo inicial y comandos ejecutados
- [ ] T006 [P] Escribir pruebas de lectura/validación en `tests/unit/test_qualys_adapter.py` — BOM, coma, comillas, multilínea, encabezado exacto, límites, campos obligatorios/opcionales, fechas, QID, CVEs, valores originales/normalizados, rechazo único · Dep: T004 · Check: las pruebas fallan antes de T010 · Evidence: rojo inicial
- [ ] T007 [P] Escribir pruebas de staging/confirmación en `tests/unit/test_qualys_service.py` — `staged` solo válido, `rejected` con errores, sin filas en `rejected`, confirmación atómica, idempotencia, cancelación, expiración, secuencia y concurrencia · Dep: T004 · Check: las pruebas fallan antes de T011 · Evidence: rojo inicial
- [ ] T008 Implementar las tablas y la migración aditiva en `src/secguard_advisor/db/models.py` y `alembic/versions/` — `qualys_imports`, `qualys_vulnerabilities`, `qualys_vulnerability_cves`, `qualys_import_issues`; estados `validating/staged/rejected/confirmed/cancelled/expired/failed`; checks e índices de `data-model.md` · Dep: T002 · Check: `uv run alembic upgrade head` y `downgrade` sobre SQLite temporal; tablas sintéticas intactas · Evidence: revisión Alembic y `pragma table_info`
- [ ] T009 Implementar políticas versionadas en `src/secguard_advisor/vulnerabilities/policies.py` — severidad, estados, grupos, evaluaciones de indicadores, prioridad conjunta y motivos · Dep: T005, T008 · Check: T005 en verde · Evidence: pruebas y salida de versiones de política
- [ ] T010 Implementar lectura y validación en `src/secguard_advisor/vulnerabilities/adapter.py` y `validation.py` — `utf-8-sig`, `csv.DictReader`, `newline=""`, 41 columnas, límites, normalización, issues, `staged`/`rejected` y resumen agregado · Dep: T006, T008, T009 · Check: T006 en verde · Evidence: pruebas y resultado de fixtures válidos/inválidos
- [ ] T011 Implementar staging, confirmación, cancelación, expiración y secuencia en `src/secguard_advisor/vulnerabilities/service.py` — no insertar filas en `rejected`, solo confirmar `staged`, idempotencia por hash, transacción corta, `confirmed_sequence`, limpieza de temporales · Dep: T007, T008, T010 · Check: T007 en verde · Evidence: pruebas y estados observados
- [ ] T012 Actualizar la documentación del corte en `README.md`, `AGENTS.md` y `.specify/memory/constitution.md` con el esquema, la política de rechazo único y la sección «Vulnerabilidades» — Dep: T008, T009, T010, T011 · Check: revisión de coherencia con `spec.md`/`plan.md` · Evidence: diff y decisión registrada

**Checkpoint**: base compartida lista; las historias pueden comenzar.

## Phase 3: User Story 1 - Importar y consultar (P1) 🎯 MVP

**Goal**: caso → Vulnerabilidades → cargar CSV → validar → preview → confirmar → consultar.

**Independent Test**: con el fixture sintético válido, la sección muestra el formulario, el archivo
queda `staged`, la confirmación crea un snapshot y `findings_query` devuelve los conteos del snapshot.

- [ ] T013 [P] [US1] Escribir pruebas de contrato de rutas en `tests/contract/test_vulnerabilities_routes.py` — sección, formulario, `validate` con `staged`/`rejected`, preview, confirmar, cancelar, 404 de otro caso, 413/422, sin control de aceptación parcial · Dep: T008, T010, T011 · Check: fallan antes de T015–T017 · Evidence: rojo inicial
- [ ] T014 [P] [US1] Escribir integración SQLite en `tests/integration/test_qualys_import_sqlite.py` — importar fixture válido, confirmar, consultar conteos, reimportar mismo hash y comprobar cero duplicados; `rejected` no consultable · Dep: T008, T010, T011 · Check: falla antes de T017/T019 · Evidence: rojo inicial
- [ ] T015 [US1] Implementar rutas en `src/secguard_advisor/web/routes/vulnerabilities.py` y registrar el router en `src/secguard_advisor/web/app.py` — GET sección/historial/formulario/preview, POST validate/confirm/cancel, resolución de caso y errores · Dep: T013 · Check: pruebas de rutas de estructura en verde · Evidence: rutas y respuestas observadas
- [ ] T016 [US1] Implementar vistas y plantillas en `src/secguard_advisor/web/templates/vulnerabilities/` y el enlace de navegación en `src/secguard_advisor/web/templates/components/navigation.html` y `web/navigation.py` — «Vulnerabilidades», formulario sin ruta/manifiesto, preview, resumen, tabla, estados vacíos/error, `pending`, doble envío · Dep: T015 · Check: T013 en verde; HTML sin recursos externos · Evidence: pruebas de contrato y captura local
- [ ] T017 [US1] Conectar validación, preview, confirmación y cancelación en `src/secguard_advisor/vulnerabilities/service.py` y `web/routes/vulnerabilities.py` — `staged`/`rejected`, confirmación solo de `staged`, cancelación y errores · Dep: T011, T015 · Check: T013 y T014 en verde · Evidence: pruebas y estados de importación
- [ ] T018 [P] [US1] Escribir pruebas unitarias de consulta importada en `tests/unit/test_qualys_query.py` — último snapshot confirmado, `origin=imported`, conteos, CVE múltiple sin multiplicar, detalle y snapshot nulo · Dep: T008, T010 · Check: fallan antes de T019 · Evidence: rojo inicial
- [ ] T019 [US1] Implementar consulta básica en `src/secguard_advisor/vulnerabilities/queries.py` y la fachada de `src/secguard_advisor/tools/findings.py` — solo `confirmed`, snapshot por defecto, total/grupos, CVE con subconsulta, detalle · Dep: T018, T008, T010 · Check: T018 en verde · Evidence: pruebas y SQL/ORM observado
- [ ] T020 [US1] Actualizar decisión y respuesta en `src/secguard_advisor/conversation/prompts.py`, `llm.py` y `nodes.py` para importados básicos — argumentos `origin`, `snapshot_id`, procedencia y presupuesto de la nueva definición/resultados · Dep: T019 · Check: pruebas de prompt y presupuesto en verde; sin `Results` completo al modelo · Evidence: versión de prompt y medición
- [ ] T021 [US1] Actualizar `README.md` y `AGENTS.md` con el flujo «Vulnerabilidades», los límites y la limitación de formato — Dep: T016, T020 · Check: documentos coherentes con `quickstart.md` · Evidence: diff y enlaces
- [ ] T022 [US1] Añadir prueba de contrato de `findings_query` importada en `tests/contract/test_findings_query_contract.py` — procedencia, snapshot, totales y detalle sin `case_id` · Dep: T019 · Check: verde y sin `case_id` en esquema/resultado · Evidence: salida

**Checkpoint**: US1 funcional; importación y consulta básica verificables.

## Phase 4: User Story 2 - Instantáneas históricas (P2)

**Goal**: archivos distintos crean snapshots; el último es el default; se puede seleccionar uno
anterior; no se suman ni se infiere remediación.

**Independent Test**: importar fixture válido, luego segundo fixture; existen dos snapshots; el
default es el segundo; seleccionar el primero devuelve sus totales, sin suma.

- [ ] T023 [P] [US2] Escribir pruebas de snapshots en `tests/unit/test_qualys_snapshots.py` — secuencia, último confirmado, selección anterior, mismo hash idempotente, archivo distinto, ausencia sin remediación, snapshot fijado · Dep: T011 · Check: fallan antes de T024/T026 · Evidence: rojo inicial
- [ ] T024 [US2] Implementar historial y selector en `src/secguard_advisor/vulnerabilities/service.py`, `queries.py`, `web/routes/vulnerabilities.py` y `web/templates/vulnerabilities/_history.html` — lista de snapshots, selección, default y estado vacío · Dep: T023, T015, T017 · Check: T023 en verde para historial/selección · Evidence: pruebas y HTML
- [ ] T025 [P] [US2] Escribir integración de snapshots en `tests/integration/test_qualys_snapshots.py` — dos archivos, no suma, idempotencia, ausencia no remediación · Dep: T024 · Check: falla antes de T026 si aplica · Evidence: rojo/verde
- [ ] T026 [US2] Fijar el snapshot en la primera herramienta del turno en `src/secguard_advisor/conversation/graph.py` y `nodes.py` — `selected_import_id` en estado, reutilización, resumen histórico, sin cambio durante la respuesta · Dep: T019, T024 · Check: T023/T025 en verde; prueba de concurrencia · Evidence: estado y `run_tool_calls`
- [ ] T027 [US2] Actualizar `quickstart.md`, `README.md` y `AGENTS.md` con snapshots, selector y ausencia de inferencia de remediación — Dep: T024, T026 · Check: pasos reproducibles y sin contradicción · Evidence: diff y ejecución del quickstart sintético

**Checkpoint**: snapshots históricos y selección reproducibles.

## Phase 5: User Story 3 - Estado, severidad, prioridad y procedencia (P3)

**Goal**: consultar estado, severidad 1–5, prioridad e indicadores; separar orígenes y conservar
procedencia.

**Independent Test**: el fixture mixto muestra `Fixed`/desconocido/indicadores; la tabla y
`findings_query` separan grupos y orígenes; un filtro de severidad sin origen en un caso mixto se
rechaza.

- [ ] T028 [P] [US3] Escribir pruebas de estado/severidad/prioridad en `tests/unit/test_qualys_status_priority.py` — cuatro estados, desconocido manual, 1–5, ambos/solo uno/vacío/negativo/indeterminado, `Fixed` como antecedente, sin P1–P4 · Dep: T009, T010 · Check: fallan antes de T030 · Evidence: rojo inicial
- [ ] T029 [P] [US3] Escribir contrato de `findings_query` extendido en `tests/contract/test_findings_query_contract.py` — `origin`, `snapshot_id`, `status_group`, `severity_level`, prioridad, indicadores, `group_by`, filtros ambiguos y compatibilidad sintética · Dep: T019 · Check: fallan antes de T031/T032 · Evidence: rojo inicial
- [ ] T030 [US3] Implementar estado/severidad/prioridad en `src/secguard_advisor/vulnerabilities/policies.py`, `validation.py`, `queries.py` y `web/templates/vulnerabilities/_table.html` — grupos, etiquetas, motivo de prioridad, revisión manual y filtros · Dep: T028, T009, T010 · Check: T028 en verde · Evidence: pruebas y HTML
- [ ] T031 [US3] Extender `findings_query` en `src/secguard_advisor/tools/findings.py` y `vulnerabilities/queries.py` — esquema, origen, snapshot, estado, severidad numérica/etiqueta, prioridad, indicadores y `group_by` · Dep: T029, T019, T030 · Check: T029 en verde · Evidence: contrato y pruebas
- [ ] T032 [US3] Actualizar decisión/respuesta y presupuesto en `src/secguard_advisor/conversation/prompts.py`, `llm.py` y `nodes.py` — origen, escalas, snapshot, estado, prioridad y resumen; sin `Results` al modelo · Dep: T031 · Check: pruebas de prompt/presupuesto; T029 en verde · Evidence: versión de prompt y tokens
- [ ] T033 [US3] Implementar tabla y filtros en `src/secguard_advisor/web/routes/vulnerabilities.py`, `queries.py` y `web/templates/vulnerabilities/` — snapshot, estado, severidad, prioridad, indicadores, activo, QID, CVE, detalle, estados vacíos y revisión manual · Dep: T016, T030, T031 · Check: contrato de rutas y HTML en verde · Evidence: pruebas y captura
- [ ] T034 [US3] Escribir integración de orígenes y compatibilidad en `tests/integration/test_qualys_origins.py` — sintético+importado, desglose, filtro ambiguo, CVE múltiple, aislamiento y presupuesto · Dep: T031, T032 · Check: verde; `pytest -m integration` focalizado · Evidence: salida real
- [ ] T035 [US3] Actualizar `contracts/findings-query.md`, `README.md`, `AGENTS.md` y `.specify/memory/constitution.md` con escalas, estados, prioridad, snapshots y orígenes — Dep: T031, T032, T034 · Check: coherencia documental y registro de decisión · Evidence: diff y revisión

**Checkpoint**: las tres historias son independientemente verificables.

## Phase 6: Polish & Cross-Cutting

- [ ] T036 [P] Escribir pruebas de privacidad en `tests/unit/test_qualys_privacy.py` — sin filas/IP/activos/resultados/indicadores en LangSmith, logs, callbacks, prompts externos; `Results` no enviado al modelo; alcance por caso y redacción · Dep: T031, T032 · Check: verde y payloads inspeccionados · Evidence: salida y payload de prueba
- [ ] T037 [P] Ejecutar regresión del primer incremento con `make check` y los contratos/aceptación existentes — sin modificar datos sintéticos, citas, memoria, ejecuciones ni `findings_query` sintético · Dep: T035 · Check: suite rápida y contratos 001 en verde · Evidence: salida con fecha
- [ ] T038 [P] Escribir aceptación Playwright en `tests/acceptance/test_vulnerabilities_ui.py` — sección, formulario, validar, preview, confirmar, cancelar, historial, selector, tabla, estados vacíos, prioridad visible, carga, doble envío; escritorio 1440, móvil 390 y 320; consola y recursos · Dep: T033, T035 · Check: `uv run pytest tests/acceptance/test_vulnerabilities_ui.py` · Evidence: capturas y salida
- [ ] T039 [P] Escribir aceptación real local en `tests/integration/test_qualys_import_real.py` — rutas `../14-Qualys_Hallazgos_Active_New_ReOpened.csv` y manifiesto, skip si faltan, hash/bytes/662/631/10/21/0, importar en SQLite temporal, contrastar 129/8/8 sin forzar, no copiar datos · Dep: T031, T033 · Check: `make test-integration` focalizado o skip documentado · Evidence: salida con fecha, sin filas reales en logs
- [ ] T040 Ejecutar comprobaciones finales — `make check`, `make test-integration`, `uv run pre-commit run --all-files`, `make assets`, migración sobre almacenamiento temporal y aislamiento de datos; registrar fallos reales sin exclusiones — Dep: T036, T037, T038, T039 · Check: salidas completas · Evidence: resultados, fecha y entorno
- [ ] T041 Actualizar documentación de cierre en `README.md`, `AGENTS.md`, `specs/002-qualys-findings-import/quickstart.md` y `docs/evidencia/` — estado de implementación, comandos, fixtures, limitaciones, aceptación real y pendientes; no marcar validaciones humanas como ejecutadas · Dep: T040 · Check: cada afirmación tiene evidencia localizable · Evidence: diff, capturas y reporte

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup**: T001 primero; T002 y T003 después.
- **Foundational**: T004–T012 dependen de Setup y bloquean las historias. T008–T011 son la cadena
  crítica de esquema/validación/staging.
- **US1**: T013–T022 dependen de Foundational. T015–T017 son la cadena de UI/servicio; T018–T020 la
  cadena de consulta/prompt; T022 es contrato de cierre.
- **US2**: T023–T027 dependen de US1 (servicio y consulta básica).
- **US3**: T028–T035 dependen de US1 y de las políticas/consulta; T031–T033 son la cadena de
  contrato/consulta/UI.
- **Polish**: T036–T041 dependen de US1–US3; T040 depende de T036–T039; T041 depende de T040.

### Critical Path

`T001 → T002 → T004 → T006 → T008 → T010 → T011 → T013 → T015 → T017 → T018 → T019 → T020 →
T023 → T024 → T026 → T028 → T030 → T031 → T032 → T033 → T036/T038/T039 → T040 → T041`

### Parallel Opportunities

- T004, T005, T006, T007 son archivos distintos; T005–T007 dependen de T004.
- T013 y T014 son archivos distintos después de Foundational.
- T018 es independiente de T013–T017 una vez implementado T010.
- T023, T025 y T028/T029 son suites/archivos distintos dentro de sus fases, respetando sus
  dependencias.
- T036, T037, T038 y T039 son archivos distintos una vez cerrados T031–T035.

## Coverage Map

| Requisitos | Tareas |
|---|---|
| FR-001..FR-006 | T006, T008, T010, T013, T015 |
| FR-007..FR-010 | T007, T011, T023, T024, T026 |
| FR-011..FR-014 | T007, T010, T011, T013, T017 |
| FR-015..FR-016b | T009, T010, T011, T023, T028, T030 |
| FR-017..FR-020 | T009, T010, T028, T030 |
| FR-021..FR-026 | T005, T009, T028, T030 |
| FR-027..FR-035 | T018, T019, T020, T023, T026, T029, T031, T032, T034 |
| FR-036..FR-038 | T015, T016, T024, T033, T038 |
| FR-039..FR-041 | T003, T012, T021, T036, T039, T041 |
| FR-042..FR-045 | T003, T011, T026, T034, T037, T041 |
| SC-001..SC-004 | T010, T011, T017, T023, T025, T039 |
| SC-005..SC-008 | T010, T028, T030, T031, T034, T039 |
| SC-009..SC-012 | T028, T030, T031, T032, T034, T039 |
| SC-013..SC-015 | T016, T026, T033, T034, T038 |
| SC-016..SC-018 | T036, T038, T039, T040 |

## Implementation Strategy

1. **Corte 1 — Base y validación** (T001–T012): rama, esquema, políticas, parser, validación,
   staging/rechazo y documentación. No produce UI.
2. **Corte 2 — MVP US1** (T013–T022): formulario, preview, confirmación, consulta básica y prompt.
3. **Corte 3 — Snapshots US2** (T023–T027): historial, selector, fijación y ausencia de remediación.
4. **Corte 4 — Estado/severidad/prioridad US3** (T028–T035): grupos, indicadores, orígenes y tabla.
5. **Corte 5 — Privacidad, regresión y aceptación** (T036–T041): trazas, Playwright, archivo real,
   checks finales y documentación.

**Primer corte recomendado**: T001–T012. No ejecutar todavía; es la base que permite validar el
rechazo único y los snapshots antes de tocar la interfaz.

## Checks

- IDs únicos y secuenciales.
- Dependencias sin ciclos.
- Cada tarea tiene ruta, dependencia, check y evidencia.
- No se duplican componentes de 001: se reutilizan shell, `pending`, `findings_query`, `CaseScope`,
  presupuesto, memoria y ejecución.
- No se incluye el CSV real en fixtures ni documentación.
- No se generan tareas para P1–P4, entrenamiento, conectores, exportaciones o remediación.
