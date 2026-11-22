# 004 — Último resultado (Corte 4 completado)

**Fecha**: 2026-11-22 11:55–12:15 (America/Bogota, `-05`)
**Rama**: `004-qdrant-vector-index`
**Alcance**: Corte 4, T054–T064 (11 tareas). **Acumulado: T001–T064 = 64 de 82 tareas.**
**Backend**: Qdrant es el índice de la aplicación; Chroma se conserva hasta el Corte 6. SQLite sigue
siendo la fuente de verdad. No se declara aceptación de 004.

## Registro del Corte 3 (corrección de trazabilidad)

La corrección del commit `0413562` se cerró con estas comprobaciones reales el **2026-11-22 11:51**:

```text
make check → 517 passed, 35 deselected
uv run pre-commit run --all-files → Passed
```

No había un registro previo con resultados; este es el registro actual, no una reconstrucción
histórica.

## Estado por tarea

| Tarea | Estado | Evidencia |
|---|---|---|
| T054 pruebas del primer documento | Completada | `tests/unit/test_qdrant_first_document.py` (5 pruebas). |
| T055 primer documento y convergencia | Completada | Validación de generación, publicación tras validar, fallo de commit SQLite y reintento. |
| T056 pruebas de alcance | Completada | `tests/contract/test_qdrant_scope_errors.py` (6 pruebas). |
| T057 alcance esperado desde SQLite | Completada | `expected_chunks` en `search.py`; omite alcances vacíos y falla si hay datos sin alias. |
| T058 integración del primer documento | Completada | `tests/integration/test_qdrant_first_document_flow.py` (3 pruebas). |
| T059 verificación US6 | Completada | 14 pruebas del bloque en verde. |
| T060 pruebas de recuperación | Completada | `tests/integration/test_qdrant_recovery.py` (2 pruebas). |
| T061 recuperación y alias anterior | Completada | Reconstrucción fallida conserva el alias; reintento termina bien. |
| T062 pruebas por alcance | Completada | `tests/integration/test_qdrant_partial_scopes.py` (2 pruebas). |
| T063 estado por alcance | Completada | Alcance válido se publica; el fallido no; reporte global `partial`. |
| T064 verificación US5 | Completada | 4 pruebas del bloque en verde. |

## Cambios realizados

- `documents/service.py`: `_write_index` crea generación, sube puntos y valida antes de publicar el
  alias del primer documento; `_mark_available` se aísla y un fallo de commit SQLite marca la versión
  como `failed` (`sqlite_commit_failed`), habilitando el reintento.
- `retrieval/search.py`: `expected_chunks(session, scope)` calcula lo esperado desde SQLite; se omiten
  alcances vacíos, se conserva el error clasificado si hay datos sin alias y el fallo de Qdrant no se
  convierte en abstención.
- Ajustes mínimos documentados: `tests/unit/test_retrieval.py` (alcances vacíos no consultan el
  índice), `tests/contract/test_qdrant_routes.py` y `tests/integration/test_qdrant_availability.py`
  siembran documentos esperados para provocar el fallo de índice.
- Pruebas nuevas: primer documento (unit e integración), alcance vacío/ausente, recuperación y
  alcances parciales.

## Comandos y resultados

```text
uv run pytest tests/unit/test_qdrant_first_document.py \
  tests/integration/test_qdrant_first_document_flow.py \
  tests/contract/test_qdrant_scope_errors.py \
  tests/integration/test_qdrant_recovery.py \
  tests/integration/test_qdrant_partial_scopes.py → 21 passed
uv run pytest (regresiones de recuperación, evidencia, citas, disponibilidad,
  reconstrucción, estado, versiones y rutas) → 49+ passed
make check → 535 passed, 35 deselected
uv run pre-commit run --all-files → Passed
```

## Embebido frente a servidor real

- **Embebido (automatizado)**: primer documento, fallo de escritura/validación/commit, reintento,
  alcance vacío/ausente, recuperación y parciales.
- **Servidor real + EmbeddingGemma + Ollama**: flujo de interfaz validado con Playwright MCP sobre
  Qdrant 1.20.0 y un caso ficticio:
  1. Crear caso.
  2. Subir `sample.pdf` como primer documento: queda **Disponible**, una versión, un fragmento.
  3. Consultar: indicador «Consultando las fuentes y preparando la respuesta…» visible.
  4. Segunda consulta: respuesta con **cita válida** («Hola mundo desde SecGuard Advisor»), control
     automático de cita literal «válida», versión no declarada y página 1. Sin duplicados: un
     documento y una versión.
  5. La primera consulta se abstuvo por citas no verificables; se reformuló. Es comportamiento del
     generador, no del índice.
- Captura: `docs/evidencia/004-corte-4/chat-citation.png`.

## Limitaciones

- Sin calibración de umbral (Corte 6).
- Chroma y sus datos permanecen.
- El volumen local de Qdrant conserva colecciones de smokes propios (`cut2-*`, `cut3-smoke`,
  `cut4-ui`).
- La aceptación integral de 004 sigue pendiente.

## Commits

`4e26306` alcance esperado · `500a64e` primer documento validado · `1a80c73` recuperación y parciales ·
`0413562` corrección de trazabilidad (Corte 3).

## Siguiente paso

Corte 5 (T065–T069): aislamiento de instancias y lock entre procesos. No se inició T065.

## Corrección de concurrencia del Corte 4 (2026-11-22 12:26)

**Causa**: `_process_version` liberaba el lock de ingesta antes de `_mark_available`. Una
reconstrucción podía ejecutarse en esa ventana, excluir la versión aún no disponible y publicar otra
generación; después la ingesta confirmaba la versión como disponible con sus puntos fuera del índice
activo. Reproducido: segundo documento no recuperable tras `rebuild = completed` e ingesta `created`.

**Solución**: la confirmación de disponibilidad (`_mark_available`) y el tratamiento del fallo de
commit (`_finish_failed`) se ejecutan dentro del lock de ingesta. Las transacciones SQLite siguen
siendo cortas, SQLite sigue siendo la fuente de verdad y no se promete atomicidad entre Qdrant y
SQLite. El context manager libera el lock ante éxito, excepción o fallo de commit. No se añadió otra
primitiva ni un bloqueo global.

**Regresión** (`tests/integration/test_qdrant_ingestion_lock.py`):

- Segundo documento con contenido distinto (`sample.md`, no `duplicate`); durante `_mark_available` el
  lock lo posee `ingestion` y `rebuild` se rechaza con `ingestion_in_progress`.
- Tras la ingesta el lock queda libre; `rebuild` posterior es `completed` y ambos documentos son
  recuperables.
- Fallo de commit: lock liberado, versión `failed`; reintento `created` y conteo igual a los
  fragmentos, sin duplicados.

**Comandos**: pruebas afectadas de primer documento, reconstrucción, recuperación, parciales y lock →
21 passed; `make check` → 537 passed; `pre-commit` → Passed.

Contratos sincronizados: `contracts/rebuild.md`, `data-model.md` y `plan.md` indican que el lock cubre
la confirmación de disponibilidad. Avance: **64/82**, sin marcar tareas posteriores.
