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

- [x] T001 Crear o cambiar a la rama `002-qualys-findings-import` desde el estado actual, conservando los commits documentales; no hacer reset, rebase ni reescritura — Dep: ninguna · Check: `git branch --show-current` y `git log --oneline -3` · Evidence: rama y hashes observados, sin cambios de historia
- [x] T002 Crear el esqueleto del módulo y los parámetros de límites/políticas en `src/secguard_advisor/vulnerabilities/__init__.py` y `src/secguard_advisor/config.py` — límites 10 MiB, 10.000 filas, 20.000 caracteres por campo, 1.000 CVE; versiones `qualys-csv-1`, `project-severity-1-5-v1`, `qualys-status-v1`, `qualys-evidence-both-v1` · Dep: T001 · Check: import del módulo y valores por defecto en una prueba rápida · Evidence: salida de import y valores observados
- [x] T003 [P] Registrar en `.specify/memory/constitution.md` las decisiones de gobierno — instantáneas independientes, rechazo único, sección «Vulnerabilidades», formato CSV definido y diferimiento de P1–P4 al incremento 3; no duplicar aquí la documentación de comportamiento — Dep: T001 · Check: decisiones sin contradicción con `spec.md` y `plan.md`; el formato CSV deja de estar pendiente; P1–P4 queda diferido — Evidence: diff del registro de decisiones y versión constitucional

## Phase 2: Foundational (bloquea las historias)

**Propósito**: esquema, políticas, parser, validación y staging compartidos. Ninguna historia puede
cerrarse sin estos componentes.

- [x] T004 [P] Crear fixtures sintéticos representativos en `tests/fixtures/files/qualys_synthetic_valid.csv`, `qualys_synthetic_second.csv`, `qualys_synthetic_mixed.csv`, `qualys_synthetic_invalid_header.csv`, `qualys_synthetic_invalid_rows.csv`, `qualys_synthetic_empty.csv`, `qualys_synthetic_manifest.json` y `tests/fixtures/qualys.py` — BOM, comas, comillas, multilínea, cuatro estados, desconocido, severidades 1–5, CVE de 4–7 dígitos, ambos/solo uno/vacío/negativo/indeterminado, filas repetidas, archivo vacío y manifiesto sintético; sin datos reales · Dep: T002 · Check: cada fixture se parsea con el lector de prueba y sus conteos esperados quedan declarados · Evidence: archivos y conteos sintéticos
- [x] T005 [P] Escribir pruebas de políticas en `tests/unit/test_qualys_policies.py` — severidad 1 Informativa a 5 Crítica, estados admitidos/desconocidos, grupos de estado, evaluación de `Exploitability` y `Associated Malware`, prioridad conjunta, versiones · Dep: T004 · Check: pruebas de políticas en verde · Evidence: `test_qualys_policies.py` verde; RED no observado por ejecución conjunta del corte
- [x] T006 [P] Escribir pruebas de lectura/validación en `tests/unit/test_qualys_adapter.py` — BOM, coma, comillas, multilínea, encabezado exacto, límites, campos obligatorios/opcionales, fechas, QID, CVE de 4–7 dígitos, archivo vacío, valores originales/normalizados, rechazo único · Dep: T004 · Check: pruebas de lectura/validación en verde · Evidence: `test_qualys_adapter.py` verde; RED no observado por ejecución conjunta del corte
- [x] T007 [P] Escribir pruebas de staging/confirmación en `tests/unit/test_qualys_service.py` — `staged` solo válido, `rejected` con errores, archivo vacío `empty_file` con `csv_bytes=0`, sin filas en `rejected`, confirmación atómica, idempotencia, cancelación, expiración, secuencia y concurrencia · Dep: T004 · Check: pruebas de staging/confirmación en verde · Evidence: `test_qualys_service.py` verde; RED no observado por ejecución conjunta del corte
- [x] T008 Implementar las tablas y la migración aditiva en `src/secguard_advisor/db/models.py` y `alembic/versions/` — `qualys_imports`, `qualys_vulnerabilities`, `qualys_vulnerability_cves`, `qualys_import_issues`; estados `validating/staged/rejected/confirmed/cancelled/expired/failed`; `manifest_status`, conteos independientes de indicadores, checks e índices de `data-model.md` · Dep: T002 · Check: `uv run alembic upgrade head` y `downgrade` sobre SQLite temporal; tablas sintéticas intactas · Evidence: upgrade/downgrade, `alembic check` sin operaciones y tablas Qualys verificadas en SQLite temporal
- [x] T009 Implementar políticas versionadas en `src/secguard_advisor/vulnerabilities/policies.py` — severidad, estados, grupos, evaluaciones de indicadores, prioridad conjunta y motivos · Dep: T005, T008 · Check: T005 en verde · Evidence: pruebas y salida de versiones de política
- [x] T010 Implementar lectura y validación en `src/secguard_advisor/vulnerabilities/adapter.py` y `validation.py` — `utf-8-sig`, `csv.DictReader`, `newline=""`, 41 columnas, límites, normalización, issues, `staged`/`rejected`, archivo vacío `empty_file`, cálculo de posibles repeticiones y filas adicionales, valores de archivo no confiables y resumen agregado con distribuciones independientes de indicadores · Dep: T006, T008, T009 · Check: T006 en verde · Evidence: pruebas y resultado de fixtures válidos/inválidos/vacíos
- [x] T011 Implementar staging, confirmación, cancelación, expiración y secuencia en `src/secguard_advisor/vulnerabilities/service.py` — no insertar filas en `rejected`, solo confirmar `staged`, idempotencia por hash, transacción corta, `confirmed_sequence`, limpieza de temporales; persistir `rejected` con `csv_bytes=0` y `empty_file` — Dep: T007, T008, T010 · Check: T007 en verde · Evidence: pruebas y estados observados
- [x] T045 Implementar y probar la comparación con el manifiesto de referencia en `src/secguard_advisor/vulnerabilities/validation.py`, `service.py` y `tests/unit/test_qualys_manifest.py` — hash, bytes, filas, columnas y conteos de estado; `manifest_status` `absent`/`matched`/`mismatch`/`invalid`; manifiesto sintético en pruebas; parámetro del servicio de aceptación, no formulario ni ruta HTTP; el formulario sigue aceptando solo el CSV · Dep: T008, T010, T011 · Check: coincidencia acepta, ausencia no bloquea y cualquier diferencia o manifiesto inválido deja `rejected`; sin control de aceptación parcial · Evidence: pruebas y fixture de manifiesto
- [x] T046 Añadir pruebas de posibles repeticiones en `tests/unit/test_qualys_repeats.py` — cantidad de grupos repetidos, filas adicionales, conservación de todas las filas válidas y ausencia de deduplicación silenciosa; no afirmar identidad estable entre reportes · Dep: T004, T010 · Check: conteos de grupos/filas adicionales coinciden con el fixture y todas las filas válidas permanecen · Evidence: pruebas y resumen de repeticiones
- [x] T012 Documentar el comportamiento implementado en `README.md` y `AGENTS.md` — esquema, `staged`/`rejected`, `empty_file`, rechazo único y sección «Vulnerabilidades»; reemplazar la frase de AGENTS que afirma que `findings_query` nunca presenta importaciones Qualys por la distinción sintético/importado, sin declarar operativo lo no implementado; la decisión de gobierno queda en T003 — Dep: T008, T009, T010, T011, T045 · Check: revisión de coherencia con `spec.md`/`plan.md` y AGENTS sin contradicción — Evidence: diff de README/AGENTS

**Checkpoint**: base compartida lista; las historias pueden comenzar.

## Phase 3: User Story 1 - Importar y consultar (P1) 🎯 MVP

**Goal**: caso → Vulnerabilidades → cargar CSV → validar → preview → confirmar → consultar.

**Independent Test**: con el fixture sintético válido, la sección muestra el formulario, el archivo
queda `staged`, la confirmación crea un snapshot y `findings_query` devuelve los conteos del snapshot.

- [x] T013 [P] [US1] Escribir pruebas de contrato de rutas en `tests/contract/test_vulnerabilities_routes.py` — sección, formulario, `validate` con `staged`/`rejected`, preview, confirmar, cancelar, 404 de otro caso, 413/422, sin control de aceptación parcial · Dep: T008, T010, T011 · Check: pruebas de contrato de rutas en verde · Evidence: `test_vulnerabilities_routes.py` verde; RED no observado por ejecución conjunta
- [x] T014 [P] [US1] Escribir integración SQLite en `tests/integration/test_qualys_import_sqlite.py` — importar fixture válido, confirmar, consultar conteos, reimportar mismo hash y comprobar cero duplicados; `rejected` no consultable · Dep: T008, T010, T011 · Check: integración SQLite en verde · Evidence: `test_qualys_import_sqlite.py` verde; RED no observado por ejecución conjunta
- [x] T015 [US1] Implementar rutas en `src/secguard_advisor/web/routes/vulnerabilities.py` y registrar el router en `src/secguard_advisor/web/app.py` — GET sección/historial/formulario/preview, POST validate/confirm/cancel, resolución de caso y errores · Dep: T013 · Check: pruebas de rutas de estructura en verde · Evidence: rutas y respuestas observadas
- [x] T016 [US1] Implementar vistas y plantillas en `src/secguard_advisor/web/templates/vulnerabilities/` y el enlace de navegación en `src/secguard_advisor/web/templates/components/navigation.html` y `web/navigation.py` — «Vulnerabilidades», formulario sin ruta/manifiesto, preview, resumen, tabla, dos estados vacíos («sin importaciones confirmadas» y «sin registros para estos filtros»), autoescape de todo el contenido CSV, ausencia de `Results` completo y de `|safe`, `pending` y doble envío; los valores de archivo se tratan como datos no confiables · Dep: T015 · Check: T013 en verde; HTML sin recursos externos ni HTML inyectado · Evidence: pruebas de contrato y captura local
- [x] T017 [US1] Conectar validación, preview, confirmación y cancelación en `src/secguard_advisor/vulnerabilities/service.py` y `web/routes/vulnerabilities.py` — `staged`/`rejected`, confirmación solo de `staged`, cancelación y errores · Dep: T011, T015 · Check: T013 y T014 en verde · Evidence: pruebas y estados de importación
- [x] T018 [P] [US1] Escribir pruebas unitarias de consulta importada en `tests/unit/test_qualys_query.py` — último snapshot confirmado, `origin=imported`, conteos, CVE múltiple sin multiplicar, detalle y snapshot nulo · Dep: T008, T010 · Check: pruebas de consulta importada en verde · Evidence: `test_qualys_query.py` verde; RED no observado por ejecución conjunta
- [x] T019 [US1] Implementar consulta básica en `src/secguard_advisor/vulnerabilities/queries.py` y la fachada de `src/secguard_advisor/tools/findings.py` — solo `confirmed`, snapshot por defecto, total/grupos, CVE con subconsulta, detalle · Dep: T018, T008, T010 · Check: T018 en verde · Evidence: pruebas y SQL/ORM observado
- [x] T020 [US1] Actualizar decisión y respuesta en `src/secguard_advisor/conversation/prompts.py`, `llm.py` y `nodes.py` para importados básicos — argumentos `origin`, `snapshot_id`, procedencia y presupuesto de la nueva definición/resultados · Dep: T019 · Check: pruebas de prompt y presupuesto en verde; sin `Results` completo al modelo · Evidence: versión de prompt y medición
- [x] T021 [US1] Actualizar `README.md` y `AGENTS.md` con el flujo «Vulnerabilidades», los límites y la limitación de formato — Dep: T016, T020 · Check: documentos coherentes con `quickstart.md` · Evidence: diff y enlaces
- [x] T022 [US1] Añadir prueba de contrato de `findings_query` importada en `tests/contract/test_findings_query_contract.py` — procedencia, snapshot, totales y detalle sin `case_id` · Dep: T019 · Check: verde y sin `case_id` en esquema/resultado · Evidence: salida

**Checkpoint**: US1 funcional; importación y consulta básica verificables.

### US1 — Evidencia ejecutada

- **T013/T015/T016/T017**: rutas, formulario, preview, confirmación y cancelación implementados; pruebas de contrato de rutas en verde.
- **T014**: integración SQLite con importación, confirmación, consulta, reimportación idempotente y rechazo no consultable.
- **T018/T019**: consulta básica importada con último snapshot confirmado, origen, grupos, CVE sin multiplicación, detalle y truncamiento.
- **T020**: decisión/respuesta y presupuesto actualizados; prueba de conversación con resultado importado y sin `Results` en el prompt.
- **T021**: README y AGENTS actualizados con el flujo, límites y pendientes.
- **T022**: contrato de `findings_query` importada sin `case_id` ni contenido de filas en el esquema.
- **Pruebas focalizadas**: 18 passed en consulta, conversación, contrato de rutas, integración SQLite y probe HTTP real.
- **`make check`**: 388 passed, 28 deselected.
- **Probe HTTP del CSV real**: 662 registros, 631 Active, 10 New, 21 Re-Opened, manifiesto `matched`, 662 filas persistidas y reimportación sin duplicados; almacenamiento temporal y `LANGSMITH_TRACING=false`.
- **Playwright sintético**: escritorio 1440, móvil 390 y 320; formulario, preview, confirmación, rechazo, menú móvil, foco/Escape, sin desbordamiento horizontal y consola sin errores. Capturas en `docs/evidencia/002-corte-2/`.
- **T039**: no ejecutada; no se cierra aceptación integral ni T023+.

## Phase 4: User Story 2 - Instantáneas históricas (P2)

**Goal**: archivos distintos crean snapshots; el último es el default; se puede seleccionar uno
anterior; no se suman ni se infiere remediación.

**Independent Test**: importar fixture válido, luego segundo fixture; existen dos snapshots; el
default es el segundo; seleccionar el primero devuelve sus totales, sin suma.

- [x] T023 [P] [US2] Escribir pruebas de snapshots en `tests/unit/test_qualys_snapshot_selection.py` — secuencia, último confirmado, selección anterior, mismo hash idempotente, archivo distinto, ausencia sin remediación, snapshot fijado en el turno, `snapshot_locked` y confirmación concurrente de otro reporte · Dep: T011 · Check: pruebas de snapshots en verde · Evidence: `test_qualys_snapshot_selection.py` verde; RED no observado por ejecución conjunta
- [x] T024 [US2] Implementar historial y selector en `src/secguard_advisor/vulnerabilities/service.py`, `queries.py`, `web/routes/vulnerabilities.py` y `web/templates/vulnerabilities/_history.html` — lista de snapshots, selección, default y estado vacío · Dep: T023, T015, T017 · Check: T023 en verde para historial/selección · Evidence: pruebas y HTML
- [x] T025 [P] [US2] Escribir integración de snapshots en `tests/integration/test_qualys_snapshots.py` — dos archivos, no suma, idempotencia, ausencia no remediación · Dep: T024 · Check: integración de snapshots en verde · Evidence: `tests/integration/test_qualys_snapshots.py` verde; RED no observado por ejecución conjunta
- [x] T026 [US2] Fijar el snapshot en la primera herramienta del turno en `src/secguard_advisor/conversation/graph.py` y `nodes.py` — `selected_import_id` en estado, reutilización obligatoria, `snapshot_locked` ante otra instantánea, resumen histórico y ausencia de cambio durante la respuesta; un turno nuevo puede seleccionar otra · Dep: T019, T024 · Check: T023/T025 en verde; pruebas de cambio solicitado y confirmación concurrente de otro reporte · Evidence: estado y `run_tool_calls`
- [x] T027 [US2] Actualizar `quickstart.md`, `README.md` y `AGENTS.md` con snapshots, selector y ausencia de inferencia de remediación; T027 es la responsable de esta documentación — Dep: T024, T026 · Check: pasos reproducibles y sin contradicción · Evidence: diff y ejecución del quickstart sintético

**Checkpoint**: snapshots históricos y selección reproducibles.

### US2 — Evidencia ejecutada

- **T023/T024**: dos instantáneas confirmadas, última por defecto, selección anterior, URL persistente, conteos independientes, idempotencia, aislamiento y ausencia sin inferencia de remediación.
- **T025**: integración SQLite de snapshots, no suma, reimportación sin duplicados y consulta explícita.
- **T026**: `selected_import_id` fija el snapshot en la primera herramienta; solicitar otro devuelve `snapshot_locked`; una confirmación concurrente no cambia el snapshot; un turno nuevo puede seleccionar otra.
- **T027**: quickstart, README y AGENTS actualizados con historial, selector, snapshot fijo y ausencia de inferencia de remediación.
- **Menú**: renderizado comprobado; el acceso muestra únicamente «Vulnerabilidades», sin texto de datos sintéticos.
- **Pruebas focalizadas**: 14 passed en snapshots, selector, rutas e integración.
- **`make check`**: 394 passed, 29 deselected.
- **Playwright sintético**: historial, selector, instantánea histórica, persistencia por URL, escritorio 1440, móvil 390 y 320, sin desbordamiento horizontal, consola sin errores y recursos 200. Capturas en `docs/evidencia/002-corte-3/`.
- **T039**: no ejecutada; no se cierra aceptación integral ni T028+.

## Phase 5: User Story 3 - Estado, severidad, prioridad y procedencia (P3)

**Goal**: consultar estado, severidad 1–5, prioridad e indicadores; separar orígenes y conservar
procedencia.

**Independent Test**: el fixture mixto muestra `Fixed`/desconocido/indicadores; la tabla y
`findings_query` separan grupos y orígenes; un filtro de severidad sin origen en un caso mixto se
rechaza.

- [ ] T028 [P] [US3] Escribir pruebas de integración de estado/severidad/prioridad en `tests/integration/test_qualys_status_priority.py` — cuatro estados, desconocido manual, 1–5, distribuciones independientes de explotabilidad y malware, ambos positivos, `Fixed` como antecedente, sin P1–P4; no reimplementar las unitarias de políticas de T005 · Dep: T009, T010 · Check: fallan antes de T030 · Evidence: rojo inicial
- [ ] T029 [P] [US3] Escribir contrato de `findings_query` extendido en `tests/contract/test_findings_query_contract.py` — `origin`, `snapshot_id`, `status_group`, `severity_level`, prioridad, indicadores, `group_by`, filtros ambiguos y compatibilidad sintética; incluye `origin=all` con `status_group=all`, el default `origin=imported`/`pending_known`, el error `origin_required_for_status_filter` para `status_group` distinto de `all`, `filter_not_applicable` para `status_group` con `origin=synthetic` y para `snapshot_id`/prioridad/indicadores con `origin=all`/`synthetic`, y `snapshot_locked` · Dep: T019 · Check: contrato de consulta básica en verde · Evidence: `test_findings_query_contract.py` verde
- [ ] T030 [US3] Implementar consultas, filtros y presentación de estado/severidad/prioridad en `src/secguard_advisor/vulnerabilities/queries.py` y `web/templates/vulnerabilities/_table.html` — grupos, etiquetas, motivo de prioridad, revisión manual, filtros y distribuciones independientes de indicadores; reutilizar `policies.py`/`validation.py` de T009/T010, no reimplementarlos · Dep: T028, T009, T010 · Check: T028 en verde · Evidence: pruebas y HTML
- [ ] T031 [US3] Extender `findings_query` en `src/secguard_advisor/tools/findings.py` y `vulnerabilities/queries.py` — esquema, origen, snapshot, estado, severidad numérica/etiqueta, prioridad, indicadores, `group_by`, reglas de filtros exclusivos y `snapshot_locked` · Dep: T029, T019, T030 · Check: T029 en verde · Evidence: contrato y pruebas
- [ ] T032 [US3] Actualizar decisión/respuesta y presupuesto en `src/secguard_advisor/conversation/prompts.py`, `llm.py` y `nodes.py` — origen, escalas, snapshot fijado, estado, prioridad, distribuciones de indicadores y resumen; sin `Results` al modelo · Dep: T031 · Check: pruebas de prompt/presupuesto; T029 en verde · Evidence: versión de prompt y tokens
- [ ] T033 [US3] Implementar tabla y filtros en `src/secguard_advisor/web/routes/vulnerabilities.py`, `queries.py` y `web/templates/vulnerabilities/` — snapshot, estado, severidad, prioridad, indicadores, activo, QID, CVE, detalle, revisión manual y dos estados vacíos; renderizado escapado de contenido CSV, sin `Results` completo ni `|safe`; valores de archivo no confiables · Dep: T016, T030, T031 · Check: contrato de rutas y HTML en verde; ambos estados vacíos se distinguen · Evidence: pruebas y captura
- [ ] T047 [US3] Añadir pruebas de estados vacíos en `tests/contract/test_vulnerability_empty_states.py` — caso sin importaciones confirmadas frente a importación confirmada con filtros sin coincidencias; distinguir «sin importaciones confirmadas» de «sin registros para estos filtros»; ninguno afirma ausencia de vulnerabilidades ni riesgo bajo · Dep: T016, T033 · Check: ambos escenarios se muestran con textos distintos y sin inferencia de ausencia · Evidence: pruebas y HTML
- [ ] T034 [US3] Escribir integración de orígenes y compatibilidad en `tests/integration/test_qualys_origins.py` — sintético+importado, desglose, filtro ambiguo, `origin=all` con `status_group=all`, error de filtros exclusivos con `origin=all`/`synthetic`, `status_group` con `origin=synthetic` como `filter_not_applicable`, CVE múltiple, aislamiento y presupuesto · Dep: T031, T032 · Check: verde; `pytest -m integration` focalizado · Evidence: salida real
- [ ] T035 [US3] Actualizar `contracts/findings-query.md`, `README.md` y `AGENTS.md` con escalas, estados, prioridad, orígenes y la distinción sintético/importado; los snapshots y el selector histórico quedan documentados por T027; en `.specify/memory/constitution.md` solo actualizar detalles de comportamiento, sin re-registrar las decisiones de gobierno de T003 — Dep: T003, T031, T032, T034 · Check: coherencia documental; AGENTS no declara operativo lo no implementado; no duplica snapshots de T027 · Evidence: diff y revisión

**Checkpoint**: las tres historias son independientemente verificables.

## Phase 6: Polish & Cross-Cutting

- [ ] T036 [P] Escribir pruebas de privacidad de trazas, prompts, logs y callbacks en `tests/unit/test_qualys_privacy.py` — preguntas con activos, memoria/historial, argumentos y resultados de herramienta, prompts/respuestas, callbacks, nombres de archivo, logs/errores, exclusión de `Results` y valores reales de payloads externos; usar señuelos sintéticos y tracer/cliente falsos, sin datos reales · Dep: T031, T032 · Check: verde y payloads inspeccionados · Evidence: salida y payload de prueba
- [ ] T037 [P] Ejecutar regresión del primer incremento con `make check` y los contratos/aceptación existentes — sin modificar datos sintéticos, citas, memoria, ejecuciones ni `findings_query` sintético · Dep: T035 · Check: suite rápida y contratos 001 en verde · Evidence: salida con fecha
- [ ] T038 [P] Escribir aceptación Playwright en `tests/acceptance/test_vulnerabilities_ui.py` — sección, formulario, validar, preview, confirmar, cancelar, historial, selector, tabla, estados vacíos, prioridad visible, carga, doble envío; menú móvil, foco inicial/restauración, Escape, navegación por teclado, etiquetas accesibles, errores e indicadores; escritorio 1440, móvil 390 y 320; consola y recursos · Dep: T033, T035, T047 · Check: `uv run pytest tests/acceptance/test_vulnerabilities_ui.py` · Evidence: capturas y salida
- [ ] T042 [P] Escribir pruebas de privacidad de interfaz y renderizado en `tests/contract/test_vulnerability_privacy_ui.py` — contenido sintético con etiquetas/HTML señuelo, autoescape, `Results` no renderizado, ausencia de `|safe` y de valores reales en errores/preview/tabla; depende de la UI construida · Dep: T033, T035, T036 · Check: payloads y HTML sin filas/activos/resultados reales ni HTML sin escapar · Evidence: pruebas y captura
- [ ] T048 [P] Implementar el detalle histórico sobre la instantánea registrada en `src/secguard_advisor/evidence/runs.py` — usar el `snapshot_id` del resumen, no resolver de nuevo «la última» por ausencia en los argumentos originales; conservar filtros históricos, mostrar la instantánea utilizada, etiquetar «Consulta actual» y no sustituir el resumen persistido; regresión con dos instantáneas distintas · Dep: T026, T031, T033 · Check: el detalle no cambia al confirmar otro snapshot y T043 en verde · Evidence: pruebas y HTML
- [ ] T043 [P] Añadir pruebas de evidencia histórica frente a detalle actual en `tests/contract/test_run_evidence_imported.py` — el resumen original conserva snapshot, filtros, totales y procedencia; el detalle recalculado usa ese mismo snapshot, muestra la instantánea utilizada, se etiqueta «Consulta actual» y no sustituye el histórico; regresión con dos instantáneas distintas · Dep: T048 · Check: ambas vistas se distinguen y el histórico permanece · Evidence: pruebas y HTML
- [ ] T044 [P] Añadir pruebas de no-RAG en `tests/integration/test_qualys_not_rag.py` — la importación no crea `Document`/`DocumentChunk`, no indexa en Chroma, no crea citas y se consulta por SQLite/`findings_query`; una respuesta solo-herramienta conserva evidencia estructurada sin citas · Dep: T014, T034 · Check: conteos de documentos/Chroma/citas sin cambios; consulta estructurada en verde · Evidence: salida SQLite/Chroma y respuesta
- [ ] T039 Ejecutar aceptación real local en `tests/integration/test_qualys_import_real.py` — rutas `../14-Qualys_Hallazgos_Active_New_ReOpened.csv` y manifiesto opcional pasado al servicio de validación; si falta el manifiesto, `manifest_status=absent`; hash/bytes/662/631/10/21/0; estados `absent`/`matched`/`mismatch`/`invalid`; importar en SQLite temporal; contrastar distribuciones independientes de explotabilidad (129 positivas/533 indeterminadas) y malware (8 positivos/654 indeterminados) y 8 ambos, sin forzar; no copiar datos; `LANGSMITH_TRACING=false`; si faltan los archivos, registrar «no ejecutada» con motivo, nunca `skip` como aprobación · Dep: T031, T033, T036, T042, T045 · Check: ejecutada y aprobada, ejecutada y fallida, o no ejecutada con motivo; sin filas reales en logs ni servicios externos · Evidence: salida con fecha, estado y payloads
- [ ] T040 Ejecutar comprobaciones finales — `make check`, `make test-integration`, `uv run pre-commit run --all-files`, `make assets`, migración sobre almacenamiento temporal y aislamiento de datos; reportar por separado checks generales y aceptación real; si T039 no se ejecutó o falló, no declarar cierre completo — Dep: T036, T037, T038, T039, T042, T043, T044, T045, T046, T047, T048 · Check: salidas completas y estado de aceptación explícito · Evidence: resultados, fecha, entorno y pendiente
- [ ] T041 Actualizar documentación de cierre en `README.md`, `AGENTS.md`, `specs/002-qualys-findings-import/quickstart.md` y `docs/evidencia/` — estado de implementación, comandos, fixtures, limitaciones, aceptación real y pendientes; no marcar validaciones humanas como ejecutadas · Dep: T040 · Check: cada afirmación tiene evidencia localizable · Evidence: diff, capturas y reporte

---

## Corte 1 — Evidencia ejecutada

- **T001**: rama `002-qualys-findings-import` creada desde `001-consulta-documental`, sin reescritura de historia.
- **T002**: límites y versiones en `config.py` y `vulnerabilities/__init__.py`.
- **T003**: decisiones de gobierno y acuerdo del equipo registrados en la constitución.
- **T004**: fixtures sintéticos en `tests/fixtures/files/` y helper `tests/fixtures/qualys.py`.
- **T005/T009**: políticas de severidad, estado, indicadores y prioridad; pruebas unitarias verdes.
- **T006/T010**: lector y validación; BOM, comillas, multilínea, límites, archivo vacío, CVE 4–7, rechazo completo.
- **T007/T011**: staging, confirmación, cancelación, expiración, secuencia e idempotencia; pruebas verdes.
- **T008**: tablas y migración aditiva; `alembic upgrade head`, `downgrade` y `alembic check` en SQLite temporal.
- **T045**: comparación de manifiesto por hash, bytes, filas, columnas y estados; `absent`, `matched`, `mismatch`, `invalid`.
- **T046**: posibles repeticiones conservadas; sin deduplicación.
- **T012**: README y AGENTS actualizados sin presentar formulario ni consulta importada como disponibles.
- **Ajuste de alcance autorizado**: el responsable autorizó usar el CSV real filtrado en el corte 1
  para inspección estructural, construcción, validación local y comprobación en almacenamiento
  temporal. No se versionó, no se envió a servicios externos y no cierra T039.
- **Pruebas del corte**: 36 pruebas focalizadas verdes; `make check` = 372 passed, 26 deselected.
- **Probe local del CSV real**: 1 passed con `LANGSMITH_TRACING=false`, almacenamiento temporal y sin copiar el CSV.
- **Aceptación real T039**: no ejecutada; el corte no cierra aceptación integral ni funcionalidades posteriores.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup**: T001 primero; T002 y T003 después.
- **Foundational**: T004–T012, T045 y T046 dependen de Setup y bloquean las historias. T008–T011,
  T045 y T046 son la cadena crítica de esquema/validación/staging/manifiesto/repeticiones. T045 se
  ejecuta después de T011 porque `service.py` ya existe.
- **US1**: T013–T022 dependen de Foundational. T015–T017 son la cadena de UI/servicio; T018–T020 la
  cadena de consulta/prompt; T022 es contrato de cierre.
- **US2**: T023–T027 dependen de US1 (servicio y consulta básica).
- **US3**: T028–T035 y T047 dependen de US1 y de las políticas/consulta; T031–T033 son la cadena de
  contrato/consulta/UI; T047 cubre los dos estados vacíos. T035 depende además de T003 por el uso de
  sus decisiones de gobierno.
- **Polish**: T036–T044 y T048 dependen de US1–US3. T039 depende de T036, T042 y T045. T043 depende
  de T048. T040 depende de T036–T039, T042–T048; T041 depende de T040.

### Critical Path

`T001 → T002 → T004 → T006 → T008 → T010 → T011 → T045 → T013 → T015 → T017 → T018 → T019 → T020 →
T023 → T024 → T026 → T028 → T030 → T031 → T032 → T033/T047 → T036/T038/T042/T044/T048 → T043/T039 →
T040 → T041`

### Parallel Opportunities

- T004, T005, T006 y T007 son archivos distintos; T005–T007 dependen de T004. T008 puede avanzar
  después de T002 en paralelo con T004–T007.
- T013 y T014 son archivos distintos después de Foundational.
- T018 es independiente de T013–T017 una vez implementado T010.
- T023, T025 y T028/T029 son suites/archivos distintos dentro de sus fases, respetando sus
  dependencias.
- T036, T037, T038, T042, T044 y T048 son archivos distintos una vez cerrados sus prerrequisitos.
  T043 depende de T048. T039 no es paralela con T036/T042: espera la privacidad y el manifiesto.

## Coverage Map

### Requisitos funcionales

| Requisito | Tareas | Nota |
|---|---|---|
| FR-001 | T006, T010, T013, T015 | Caso resuelto por servidor |
| FR-002 | T006, T010 | Formato y 41 columnas |
| FR-003 | T008, T010, T045 | Hash, manifiesto y estados de dominio |
| FR-004 | T006, T010 | BOM, comillas y multilínea |
| FR-005 | T006, T010 | Columnas obligatorias/opcionales/desconocidas |
| FR-006 | T006, T010 | Valores originales y normalizados |
| FR-007 | T008, T011, T023, T024, T026 | Instantáneas independientes |
| FR-008 | T007, T011, T014, T023 | Idempotencia por hash |
| FR-009 | T007, T011, T023, T024, T025 | Archivo distinto e inmutabilidad |
| FR-010 | T004, T010, T046 | Repeticiones conservadas |
| FR-011 | T010, T013, T016, T017, T046 | Preview y rechazo único |
| FR-012 | T011, T013, T017 | Confirmación explícita |
| FR-013 | T007, T010, T011, T013, T017 | Rechazo completo y archivo vacío |
| FR-014 | T006, T010 | Validación por fila |
| FR-015 | T005, T009, T028, T030 | Estados admitidos y revisión manual |
| FR-016 | T009, T030, T031 | Grupos de estado |
| FR-016a | T007, T008, T011 | Estados de importación |
| FR-016b | T011, T014, T019, T023, T026 | Solo `confirmed` consultable |
| FR-017 | T005, T009, T028, T030 | Severidad 1–5 |
| FR-018 | T005, T009, T028, T030 | Sin CVSS/QDS/TruRisk/P1–P4 |
| FR-019 | T006, T010 | Fechas originales/normalizadas |
| FR-020 | T006, T010, T018, T019, T030 | CVE de 4–7 dígitos, sin multiplicar |
| FR-021 | T005, T009, T028, T030 | Indicadores separados |
| FR-022 | T005, T009, T028 | Regla de explotabilidad |
| FR-023 | T005, T009, T028 | Regla de malware |
| FR-024 | T005, T009, T028, T030 | Prioridad conjunta |
| FR-025 | T005, T009, T028, T030 | Contexto de prioridad |
| FR-026 | T005, T009, T028 | Sin P1–P4 ni remediación |
| FR-027 | T018, T019, T023, T024, T026 | Snapshot por defecto, selección y bloqueo |
| FR-028 | T018, T029, T031, T033 | Filtros y reglas de origen |
| FR-029 | T029, T031, T034 | Desglose por origen |
| FR-030 | T029, T031, T034 | Ambigüedad de severidad |
| FR-031 | T020, T026, T031, T032, T048 | Resumen histórico reproducible |
| FR-032 | T048, T043 | Detalle actual separado |
| FR-033 | T016, T019, T031, T033, T047 | Resultado vacío sin inferencia |
| FR-034 | T013, T019, T022, T029, T031 | Alcance y esquema estricto |
| FR-035 | T019, T031, T044 | Sin RAG ni citas |
| FR-036 | T015, T016 | Punto de entrada |
| FR-037 | T016, T030, T033 | Snapshot, severidad y motivo |
| FR-038 | T016, T038 | Recursos locales, carga y doble envío |
| FR-039 | T036, T039, T041, T042 | Privacidad externa |
| FR-040 | T004 | Fixtures sintéticos |
| FR-041 | T012, T021, T041 | Limitación de formato |
| FR-042 | T037 | Regresión de 001 |
| FR-043 | T037, T044 | Citas y revisión humana separadas |
| FR-044 | T013, T014, T034 | Aislamiento por caso |
| FR-045 | T008, T011, T026, T039 | Procedencia de importación |

### Criterios de éxito

| Criterio | Tareas | Nota |
|---|---|---|
| SC-001 | T010, T039, T045 | Preview y manifiesto |
| SC-002 | T010, T017 | `staged`/`rejected` |
| SC-003 | T011, T014, T023 | Idempotencia |
| SC-004 | T023, T024, T025, T026 | Snapshots y selección |
| SC-005 | T004, T010, T046 | Repeticiones |
| SC-006 | T018, T019 | CVE sin multiplicar |
| SC-007 | T005, T009, T028, T030 | Severidad |
| SC-008 | T009, T030, T031 | Grupos de estado |
| SC-009 | T028, T039 | Distribuciones independientes |
| SC-010 | T030, T033 | Prioridad y motivo |
| SC-011 | T029, T031, T034 | Orígenes y ambigüedad |
| SC-012 | T026, T031, T039, T043, T048 | Procedencia y detalle histórico |
| SC-013 | T013, T014, T034 | Aislamiento |
| SC-014 | T016, T033, T047 | Dos estados vacíos |
| SC-015 | T038 | Recorrido UI |
| SC-016 | T036, T042 | Privacidad |
| SC-017 | T006, T010, T013 | Límites |
| SC-018 | T004, T028 | `Fixed` y desconocidos |

### Tareas transversales

| Tarea | Cobertura |
|---|---|
| T001, T002 | Rama, configuración y límites para todas las historias |
| T003 | Decisiones de gobierno: FR-039..FR-041, FR-042..FR-045 y C-01/C-02 |
| T012, T021, T027, T035, T041 | Documentación de comportamiento y cierre: FR-039..FR-041, FR-042..FR-045 |
| T037 | Regresión de 001: FR-042, FR-043 |
| T040 | Checks finales y aceptación: SC-016..SC-018 |
| T048 | Detalle histórico: FR-031, FR-032, SC-012 |

## Implementation Strategy

1. **Corte 1 — Base y validación** (T001–T012, T045, T046): rama, esquema, políticas, parser,
   validación, manifiesto, repeticiones, staging/rechazo y documentación. T045 se ejecuta después de
   T011. No produce UI.
2. **Corte 2 — MVP US1** (T013–T022): formulario, preview, confirmación, consulta básica y prompt.
3. **Corte 3 — Snapshots US2** (T023–T027): historial, selector, fijación y ausencia de remediación.
4. **Corte 4 — Estado/severidad/prioridad US3** (T028–T035, T047): grupos, indicadores, orígenes,
   tabla y estados vacíos.
5. **Corte 5 — Privacidad, evidencia y aceptación** (T036–T044, T048): trazas, renderizado, histórico
   frente a actual, no-RAG, Playwright, archivo real y documentación.

**Total**: 48 tareas (T001–T048).

**Primer corte recomendado**: T001–T012, T045 y T046. No ejecutar todavía; es la base que permite
validar rechazo único, manifiesto, repeticiones y snapshots antes de tocar la interfaz. T045 requiere
T011, por lo que el orden seguro es T010 → T011 → T045.

## Checks

- IDs únicos; el orden ejecutable se define por dependencias, no solo por número.
- Dependencias sin ciclos.
- Cada tarea tiene ruta, dependencia, check y evidencia.
- No se duplican componentes de 001: se reutilizan shell, `pending`, `findings_query`, `CaseScope`,
  presupuesto, memoria y ejecución.
- No se incluye el CSV real en fixtures ni documentación.
- No se generan tareas para P1–P4, entrenamiento, conectores, exportaciones o remediación.
