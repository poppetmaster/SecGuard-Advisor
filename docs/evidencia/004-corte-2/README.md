# Corte 2 — Avance parcial (T010–T017, T023, T024, T026, T027)

**Fecha**: 2026-11-22 10:10–10:55 (America/Bogota, `-05`)
**Rama**: `004-qdrant-vector-index`
**Estado**: 12 de 33 tareas cerradas. Corte **no** completado. No se declara aceptación de 004.

## Qué se implementó

### Adaptador y colecciones (T010–T013)

- `retrieval/collections.py`: nombres físicos `secguard__<instancia>__<alcance>__<modelo>__<dim>__g<UTC>`
  y alias `...__active`; las funciones de Chroma se conservan.
- `retrieval/index.py`: `QdrantIndex` con cliente inyectable (servidor o modo embebido), UUIDv5
  determinista del `chunk_id`, payload sin texto, upsert/count/query/delete, resolución de alias y
  creación de generación/alias en el primer upsert.
- `retrieval/errors.py`: `qdrant_unavailable`, `case_index_unavailable`,
  `public_index_unavailable`, `instance_namespace_mismatch`.

### Errores y fábrica (T014–T017)

- `web/errors.py`: los seis códigos con 503/409 y mensajes en español; no se degradan a
  `internal_error`.
- `web/app.py`: la fábrica construye `QdrantIndex` desde `SECGUARD_QDRANT_URL`,
  `SECGUARD_INSTANCE_ID` y el timeout; no conecta al construir.

### Estado (T023, T024, T026, T027)

- `retrieval/status.py`: resolvedor único con `resolve_operation_state` y `terminal_status`.
- `scripts/rebuild_qdrant.py --status`: JSON con `state`, `lock_owner`, `last_terminal` y `error`;
  salida 0 para estados normales y 2 para configuración inválida, lock ilegible o reporte ilegible.
  No crea archivos, marcadores, colecciones ni embeddings.

## Evidencia observada

### RED capturados

```text
# antés del adaptador (código previo restaurado temporalmente)
ERROR tests/unit/test_qdrant_index.py
ERROR tests/contract/test_qdrant_index_contract.py
E   ImportError / símbolos nuevos ausentes

# códigos sin registrar
FAILED test_qdrant_codes_keep_their_own_code_and_status
FAILED test_qdrant_codes_are_not_demoted_to_internal_error

# resolvedor ausente
ERROR tests/unit/test_qdrant_state.py

# script --status ausente
FAILED tests/integration/test_qdrant_status.py (5 failed)
```

### GREEN

```text
uv run pytest tests/unit/test_qdrant_index.py tests/contract/test_qdrant_index_contract.py → 13 passed
uv run pytest tests/unit/test_error_messages.py → 5 passed
uv run pytest tests/contract/test_qdrant_app.py → 3 passed
uv run pytest tests/unit/test_qdrant_state.py → 10 passed
uv run pytest tests/integration/test_qdrant_status.py → 5 passed
make check → 485 passed, 35 deselected
uv run pre-commit run --all-files → Passed
```

### Comportamiento verificado

- `point_id` es estable por `chunk_id`; el payload no contiene texto.
- Dos upserts del mismo `chunk_id` dejan un solo punto.
- `delete_version` y `delete_ids` reducen el conteo esperado.
- Alias ausente → `public_index_unavailable` o `case_index_unavailable`.
- `--status` sin estado devuelve `not_started` y no crea archivos; el lock activo distingue
  `ingestion_in_progress` de `rebuild_in_progress`; los metadatos residuales con lock libre se
  ignoran; el reporte ilegible devuelve salida 2 sin repararlo.

Ejemplo de salida:

```json
{"state": "not_started", "lock_owner": null, "last_terminal": null, "error": null}
```

## Pendiente (21 tareas)

T018–T022, T025, T028–T042. En particular:

- Ingesta del corpus y demo siguen en Chroma; falta el lock de escritura en esos scripts.
- No existe reconstrucción desde SQLite ni reporte de generación/alias.
- Faltan pruebas de recuperación, aislamiento, rutas, parciales, huérfanos y fallo de turno.
- La aplicación usa Qdrant por defecto, pero el corpus aún no se ingesta en Qdrant: **no usar
  `make corpus-ingest` como fuente del índice hasta completar T018–T020**.

## Datos y servicios

No se modificó `storage/` del usuario, SQLite, Chroma ni documentos existentes. Las pruebas usan
Qdrant en modo embebido sobre directorios temporales. El servidor Qdrant estaba disponible pero no se
usó para ingesta real en este avance. No se ejecutaron migraciones ni reconstrucciones.
