# Corte 2 — Evidencia de integración con Qdrant

**Fecha**: 2026-11-22 10:10–11:35 (America/Bogota, `-05`)
**Rama**: `004-qdrant-vector-index`
**Estado**: T010–T042 completadas (42/42). No se declara aceptación de 004 ni se retira Chroma.

## Pruebas automatizadas

```text
$ uv run pytest tests/unit/test_qdrant_index.py tests/unit/test_qdrant_state.py \
  tests/unit/test_error_messages.py tests/contract/test_qdrant_index_contract.py \
  tests/contract/test_qdrant_app.py tests/contract/test_qdrant_routes.py \
  tests/contract/test_qdrant_corpus_targets.py tests/integration/test_qdrant_corpus_ingest.py \
  tests/integration/test_qdrant_rebuild.py tests/integration/test_qdrant_rebuild_failures.py \
  tests/integration/test_qdrant_status.py tests/integration/test_qdrant_retrieval.py \
  tests/integration/test_qdrant_service_lock.py
53 passed

$ make check
502 passed, 35 deselected

$ uv run pre-commit run --all-files
Todas las comprobaciones: Passed
```

RED observados directamente:

- Adaptador ausente: `ERROR tests/unit/test_qdrant_index.py` e `ImportError` de símbolos nuevos.
- Códigos sin registrar: 2 fallos en `test_error_messages.py`.
- Resolvedor ausente: `ModuleNotFoundError` en `test_qdrant_state.py`.
- `--status` ausente: 5 fallos en `test_qdrant_status.py`.

No se fabricaron fallos; las tareas restantes se validaron con GREEN e integración.

## Integración real (servidor + EmbeddingGemma)

Entorno: Docker Desktop 29.9.3, contenedor `secguard-qdrant` (imagen `v1.20.0`), Ollama
`embeddinggemma` (768), storage y corpus temporales, `SECGUARD_INSTANCE_ID=cut2-smoke`.

```text
ingest público (sample.pdf ficticio): created, 1 chunk
count público tras ingesta: 1
ingest de caso: created, 1 chunk
rebuild: partial
  public: expected=1 indexed=1 missing=0 extra=1 skipped=0
  case:   expected=1 indexed=1 missing=0 extra=0 skipped=0
search: ok, 2 hits, orígenes case_evidence + public_corpus, top score 0.1389
```

El `extra=1` público es un punto de una generación anterior del mismo servidor (smoke previo con otros
`chunk_id`): se contó como discrepancia y el alias anterior se conservó. Es la detección de huérfanos
exigida, no un fallo de la reconstrucción.

Detención: `make qdrant-down` sin `-v`; contenedor y red eliminados, volumen conservado. No se
interrumpió ningún servicio ajeno.

## Comportamientos verificados

- Ingesta y recuperación del corpus público y del documento de caso.
- Aislamiento: los documentos privados de un caso no aparecen en otro; el público sí.
- Reconstrucción repetida: nueva generación, mismo conteo, sin duplicados.
- Interrupción/fallo de embeddings: estado `failed`, sin alias nuevo.
- Fragmento con dimensión incompatible: `partial`, alias anterior conservado.
- Punto huérfano: `extra_chunks`, alias anterior conservado, nunca resuelto como cita.
- Metadatos de lock obsoletos con lock libre: no bloquean.
- `--status`: `not_started`, ingesta activa, reconstrucción activa, terminales y errores de
  configuración/lock/reporte con salida 2; sin crear ni modificar archivos.
- Errores HTTP 503 en rutas y turno detenido sin llamada al generador ni abstención.
- Lock ocupado: ingesta rechazada con `reconstruction_in_progress`; reconstrucción rechazada con
  `ingestion_in_progress`.

## Datos y servicios

No se modificó `storage/` del usuario, SQLite, Chroma, documentos, casos ni Qualys. Las pruebas
automatizadas usan Qdrant embebido y directorios temporales. El volumen local de Qdrant conserva
colecciones del smoke `cut2-smoke`, sin efecto en las pruebas.

## Pendiente del corte siguiente

Citaciones/versiones y evidencia (T043–T048), reinicio/disponibilidad (T049–T053), primer documento y
alcance vacío (T054–T059), recuperación/parciales (T060–T064), instancias/lock entre procesos
(T065–T069), retiro de Chroma, calibración y aceptación (T070–T082).
