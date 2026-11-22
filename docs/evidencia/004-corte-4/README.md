> **Registro histórico.** Este documento describe el estado del corte en su fecha. Desde el Corte 6,
> Qdrant es el único backend documental y Chroma quedó retirado del código; los archivos de Chroma
> se conservan.

# Corte 4 — Primer documento, alcance vacío y recuperación

**Fecha**: 2026-11-22 11:55–12:15 (America/Bogota, `-05`)
**Rama**: `004-qdrant-vector-index`
**Estado**: T054–T064 completadas. Acumulado T001–T064 = 64/82. No se declara aceptación de 004.

## Procedimiento reproducible

```bash
uv run pytest tests/unit/test_qdrant_first_document.py \
  tests/integration/test_qdrant_first_document_flow.py \
  tests/contract/test_qdrant_scope_errors.py \
  tests/integration/test_qdrant_recovery.py \
  tests/integration/test_qdrant_partial_scopes.py
make check
uv run pre-commit run --all-files
```

Resultados observados:

```text
bloque del Corte 4: 21 passed
make check: 535 passed, 35 deselected
pre-commit: Passed
```

## Primer documento y fallos

- El primer documento crea la generación del caso, sube los puntos y **valida los `chunk_id`** antes
  de publicar el alias; después SQLite marca la versión disponible.
- Fallo de embeddings: no se toca el índice.
- Fallo de escritura Qdrant o validación incompleta: la versión queda `failed` y no se publica alias.
- Fallo de commit SQLite después de escribir puntos/publicar alias: la versión queda `failed`
  (`sqlite_commit_failed`); la recuperación excluye la versión no disponible.
- Reintento: `delete_version` limpia los puntos del intento anterior, se reindexa y el conteo final
  coincide con los fragmentos de la versión; sin duplicados.
- Un documento posterior reutiliza el alias existente; no crea generación nueva.

## Alcance vacío frente a índice ausente

| Situación | Resultado verificado |
|---|---|
| Caso sin documentos privados | Consulta el corpus público, sin error. |
| Documentos de caso en SQLite sin alias | `case_index_unavailable`. |
| Documentos públicos en SQLite sin alias | `public_index_unavailable`. |
| Público vacío o no configurado | Se omite; el caso continúa. |
| Alias presente sin coincidencias | `empty` normal. |
| Qdrant caído con datos esperados | `qdrant_unavailable`, sin fallback ni abstención. |

## Recuperación y parciales

- Reconstrucción fallida: estado `failed`, sin alias nuevo; el alias anterior se conserva si existía.
- Reintento posterior: `completed` y alias publicado.
- Varios alcances: si el público falla y el caso valida, el global es `partial`; el caso publica su
  alias y el público no. Tras corregir el fragmento incompatible, el reintento deja ambos
  `completed`.
- Reporte por alcance con `expected`, `indexed`, `missing`, `extra`, `previous_missing`,
  `previous_extra`, `skipped` y estado.

## Servidor real y revisión visual

Qdrant 1.20.0 en Docker, EmbeddingGemma y `qwen3.5:9b` locales, instancia `cut4-ui`, storage temporal
y `LANGSMITH_TRACING=false`. Flujo con Playwright MCP:

1. `/cases/new` → crear «Caso UI Corte 4».
2. `/cases/{id}/documents` → subir `tests/fixtures/files/sample.pdf`.
3. Documento **Disponible**, una versión, un fragmento; sin duplicados.
4. `/cases/{id}/chat` → primera consulta: indicador de carga visible; el generador se abstuvo por
   citas no verificables (comportamiento del modelo, no del índice).
5. Segunda consulta («Citá textualmente…»): respuesta con cita a `sample.pdf`, página 1, cita literal
   «Hola mundo desde SecGuard Advisor»; control automático «válida»; respaldo semántico pendiente.

Captura: [`chat-citation.png`](./chat-citation.png).

## Datos y servicios

No se modificó `storage/` ni `storage/demo`; no se borraron archivos Chroma ni volúmenes. El servicio
Qdrant se detuvo con `make qdrant-down` (sin `-v`) y el almacenamiento temporal se eliminó. No se usó
el CSV privado de Qualys ni servicios externos.

## Limitaciones

- Sin calibración de umbral.
- El volumen local de Qdrant conserva colecciones de smokes propios.
- Sin aceptación integral de 004.

## Corrección: lock hasta la confirmación de disponibilidad (2026-11-22 12:26)

Defecto: `_process_version` liberaba el lock antes de `_mark_available`. Una reconstrucción podía
entrar entre los puntos escritos y el commit de disponibilidad, excluir la versión no disponible y
publicar otra generación; la ingesta luego confirmaba la versión con sus puntos fuera del índice
activo. Reproducción: segundo documento con contenido distinto, `rebuild = completed` e ingesta
`created`, pero el segundo documento no recuperable.

Corrección: `_mark_available` y el tratamiento de su fallo ocurren dentro del lock de ingesta. Sin
nueva primitiva ni bloqueo global; liberación garantizada en éxito, excepción y fallo de commit.

Regresión determinista (`tests/integration/test_qdrant_ingestion_lock.py`):

- `sample.md` como segundo documento (contenido distinto; no `duplicate`).
- Dentro de `_mark_available`, el lock pertenece a `ingestion` y `rebuild` falla con
  `ingestion_in_progress`.
- Lock libre tras la ingesta; `rebuild` posterior `completed` y ambos documentos recuperables.
- Fallo de commit: lock libre, versión `failed`; reintento sin duplicados.

```text
pruebas afectadas: 21 passed
make check: 537 passed, 35 deselected
pre-commit: Passed
```
