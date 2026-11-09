# Implementation Plan: Importación de vulnerabilidades Qualys y consulta con findings_query

**Branch**: `002-qualys-findings-import` | **Date**: 2026-11-09 | **Spec**: [spec.md](./spec.md)

**Input**: Especificación aclarada de `002-qualys-findings-import`, con snapshots independientes,
escala de severidad 1–5, cuatro estados, «Revisión manual», prioridad conjunta por explotabilidad y
malware, y sección visible «Vulnerabilidades».

## Summary

Extender el monolito modular existente con un módulo de **vulnerabilidades importadas** que conserva
cada reporte Qualys como una instantánea independiente del caso. El flujo es: abrir caso →
Vulnerabilidades → «Cargar reporte de Qualys» → «Validar archivo» → vista previa → «Confirmar
importación» → consultar registros desde la sección y mediante `findings_query`.

La importación no usa RAG ni Chroma. Parsea el CSV con la biblioteca estándar, valida estructura y
filas, conserva valores originales y normalizados en SQLite, y solo hace consultables las
instantáneas confirmadas. `findings_query` se extiende con origen, snapshot, estado, severidad
numérica/etiqueta, prioridad e indicadores, manteniendo el alcance del servidor y la compatibilidad
con hallazgos sintéticos.

## Technical Context

**Language/Version**: Python 3.14.6, `uv`, src-layout, `uv_build`.

**Primary Dependencies**: FastAPI, Jinja2, HTMX, Tailwind/Flowbite locales, SQLAlchemy, Alembic,
LangChain/LangGraph, Ollama y LangSmith opcional. No se añaden dependencias de parseo CSV: se usa
`csv`, `hashlib` y utilidades estándar.

**Storage**: SQLite local para snapshots, filas, CVEs, issues y procedencia; Alembic para migraciones
aditivas. Chroma no interviene. No se conserva el CSV como archivo en el repositorio ni se copia a
fixtures.

**Testing**: pytest con pruebas unitarias, de contrato e integración; Playwright MCP para el flujo
web y los tamaños 1440/390/320. La aceptación con el archivo real es local, fuera de Git.

**Target Platform**: Aplicación web local en un solo proceso y un worker; macOS/Linux; navegador de
escritorio y móvil.

**Project Type**: Web application monolith (FastAPI + Jinja2 + HTMX + SQLite).

**Performance Goals**: validar y previsualizar 662 filas en menos de 5 s en el equipo local; confirmar
en una transacción corta; mantener `findings_query` dentro del timeout existente de 5 s; soportar
hasta 10.000 filas sin bloquear el proceso.

**Constraints**: operación local; sin calls externos para la importación; sin datos reales en
LangSmith, logs, fixtures ni documentación; un worker; sin microservicios; sin RAG para registros
estructurados; sin P1–P4 ni remediación.

**Scale/Scope**: 662 filas de referencia, 41 columnas; límites configurables de 10 MiB, 10.000 filas,
20.000 caracteres por campo y 1.000 CVE por registro; múltiples snapshots por caso.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Evaluación | Nota |
|---|---|---|
| I. Propósito defensivo | PASS | Solo lectura, importación y consulta; no remediación ni explotación. Los datos importados se identifican como importados, no como sintéticos. |
| II. Construcción reproducible | PASS | Se mantiene Python/uv/Ruff/pytest; no se añaden dependencias de parseo. |
| III. Arquitectura modular | PASS | Nuevo módulo `vulnerabilities`; SQLite/Alembic; sin microservicios ni Chroma. |
| IV. Ejecución local | PASS | Importación y consulta locales; la inferencia sigue en Ollama. |
| V. Recuperación verificable | PASS | Los registros importados no son fragmentos ni citas RAG; no se indexan. |
| VI. Separación de datos | PASS | Los snapshots Qualys se tratan como evidencia estructurada del caso, separados de sintéticos, corpus público y evaluación. Los resultados declaran su origen. |
| VII. Seguridad | PASS | `CaseScope` en servidor; esquema estricto; sin SQL/rutas/tablas desde el modelo; aislamiento por caso. |
| VIII. Evidencia e incertidumbre | PASS | Conteos en SQLite; ausencia en un snapshot no es remediación; prioridad no es P1–P4. |
| IX. Revisión humana | PASS | La bandera operativa no adjudica P1–P4; la revisión humana por cita sigue separada. |
| X. Evaluación independiente | PASS | No se usan datos de evaluación ni se entrena un clasificador. |
| XI. Observabilidad y costos | PASS | La traza externa solo recibe metadatos acotados; no se envían filas, activos, resultados ni indicadores reales. |
| XII. Desarrollo incremental | PASS | Este es el incremento 2 de importación; no incluye clasificación, P1–P4, exportación ni operación. |

Sin violaciones que requieran justificación adicional.

## Project Structure

### Documentation (this feature)

```text
specs/002-qualys-findings-import/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── qualys-import-ui.md
│   └── findings-query.md
└── tasks.md              # NO se genera en este comando
```

### Source Code (repository root)

```text
src/secguard_advisor/
├── vulnerabilities/              # nuevo módulo de importación y consulta estructurada
│   ├── __init__.py
│   ├── adapter.py                # lectura y normalización del CSV
│   ├── policies.py               # severidad, estados, prioridad versionadas
│   ├── validation.py             # filas, issues, preview y límites
│   ├── service.py                # staging, confirmación, cancelación, snapshots
│   ├── queries.py                # consultas y conteos de snapshots
│   └── views.py                  # vistas de lectura para plantillas
├── db/models.py                  # nuevas tablas, sin tocar las sintéticas
├── tools/findings.py             # fachada de findings_query con origen/snapshot
├── conversation/
│   ├── graph.py                  # estado selected_import_id
│   ├── nodes.py                  # fijación de snapshot y ejecución de herramienta
│   ├── prompts.py                # decisión/answer con nuevos filtros y procedencia
│   └── llm.py                    # ToolDecision actualizado si cambia el esquema
├── web/
│   ├── app.py                    # router de vulnerabilidades
│   ├── navigation.py             # sección «Vulnerabilidades»
│   ├── routes/vulnerabilities.py # GET/POST del recorrido
│   └── templates/vulnerabilities/
│       ├── index.html
│       ├── _panel.html
│       ├── _import_form.html
│       ├── _preview.html
│       ├── _history.html
│       ├── _table.html
│       └── _summary.html
└── config.py                     # límites y versiones de políticas

alembic/versions/                 # migración aditiva de snapshots
tests/
├── unit/test_qualys_adapter.py
├── unit/test_qualys_policies.py
├── unit/test_qualys_service.py
├── unit/test_qualys_query.py
├── contract/test_vulnerabilities_routes.py
├── contract/test_findings_query_contract.py
├── integration/test_qualys_import_real.py
├── acceptance/test_vulnerabilities_ui.py
└── fixtures/files/qualys_*.csv    # solo sintéticos
```

**Structure Decision**: se mantiene el monolito y la separación por módulos existente. Las tablas
Qualys son nuevas y aditivas; no se reutiliza `findings` porque sus claves `asset_id`/`dataset_id`
son propias del dataset sintético y forzarían una identidad de activo no demostrada.

## Phase 0 — Research

Ver [research.md](./research.md). Decisiones principales:

- Snapshots inmutables, sin identidad estable entre reportes.
- Tablas nuevas en lugar de extender `findings`.
- Parser estándar con `utf-8-sig` y `newline=""`.
- Políticas versionadas de severidad, estado y prioridad.
- `findings_query` con origen/snapshot y resultado por origen.
- Fijación del snapshot en la primera ejecución de herramienta del turno.
- Staging en SQLite y confirmación transaccional; sin archivo CSV persistido.
- Trazas externas solo con metadatos.

## Phase 1 — Design & Contracts

- [data-model.md](./data-model.md): tablas, columnas, checks, índices, transiciones y migración.
- [contracts/qualys-import-ui.md](./contracts/qualys-import-ui.md): rutas, formulario, preview,
  confirmación, historial, errores y privacidad.
- [contracts/findings-query.md](./contracts/findings-query.md): esquema extendido, filtros,
  resultados por origen, errores y compatibilidad sintética.
- [quickstart.md](./quickstart.md): validación local con fixtures sintéticos y aceptación opcional
  con el archivo real fuera de Git.

## Construction Slices

Sin tareas numeradas; cortes revisables:

1. **Esquema y políticas**: migración aditiva, modelos, parser, severidad, estados y prioridad.
   Comprobación: unitarias de parser/políticas sobre fixtures sintéticos.
2. **Staging y confirmación**: validación, issues, preview, confirmación idempotente, cancelación,
   expiración y secuencia local. Comprobación: unitarias de servicio y concurrencia.
3. **Interfaz Vulnerabilidades**: navegación, formulario, preview, historial, resumen y tabla.
   Comprobación: contrato de rutas y Playwright.
4. **findings_query**: esquema extendido, origen/snapshot, conteos, resultado por origen y prompt.
   Comprobación: unitarias de consulta y contrato; regresión sintética.
5. **Privacidad y trazabilidad**: guardas de metadatos, redacción, pruebas de no exposición.
   Comprobación: unitarias de traza/logs y revisión de payloads.
6. **Aceptación local**: fixtures sintéticos, archivo real fuera de Git, concurrencia, aislamiento,
   reinicio y Playwright móvil. Comprobación: integración y aceptación local.

## Risks and Pending Items

- **Identidad**: no se afirma identidad estable; toda comparación entre snapshots se presenta como
  registros de reportes distintos. Riesgo de que un usuario interprete «desapareció» como remediación;
  la interfaz debe declararlo.
- **Escalas**: los filtros de severidad deben exigir origen cuando haya ambos orígenes; una conversión
  silenciosa es un defecto de aceptación.
- **Privacidad**: el prompt local puede contener activos; la traza externa no. Cualquier callback,
  error o log que incluya contenido real es bloqueante.
- **Datos reales**: no se versionan; la aceptación local debe usar almacenamiento temporal y no dejar
  copias.
- **Concurrencia**: confirmación repetida y snapshot seleccionado durante una respuesta requieren
  pruebas explícitas.
- **Fixed/desconocidos**: el archivo de referencia no contiene `Fixed`; la cobertura se hará con
  fixtures sintéticos.
- **UI**: la sección «Vulnerabilidades» es nueva; no se rediseña el shell ni se añade dashboard.
- **Rendimiento**: `Results` multilínea puede ser grande; no se envía al modelo ni se muestra completo
  en la vista previa. El límite de filas y campos es configurable.
