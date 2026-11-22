# Corte 3 — Versiones, citas, evidencia y disponibilidad

**Fecha**: 2026-11-22 11:36–11:52 (America/Bogota, `-05`)
**Rama**: `004-qdrant-vector-index`
**Estado**: T043–T053 completadas. Acumulado T001–T053 = 53/82. No se declara aceptación de 004.

## Procedimiento reproducible

```bash
uv run pytest tests/integration/test_qdrant_citations.py \
  tests/contract/test_qdrant_evidence.py \
  tests/integration/test_qdrant_restart.py \
  tests/integration/test_qdrant_availability.py \
  tests/integration/test_qualys_not_rag.py
make check
uv run pre-commit run --all-files
```

Resultados observados:

```text
citas + evidencia: 3 passed
restart + disponibilidad: 4 passed
Qualys (incluye Qdrant): 2 passed
make check: 514 passed, 35 deselected
pre-commit: Passed
```

## Versiones y citas (embebido)

- Documento con v1 y v2 vigente: la búsqueda devuelve solo los `chunk_id` de v2.
- `check_citation` sobre el fragmento de v1 devuelve `valid`: la cita histórica se resuelve desde
  SQLite y no depende de que v1 esté indexada.
- Documentos de dos casos no se cruzan; el público aparece en ambos.

## Evidencia del paso retrieve

`RunStep.detail_json` del paso `retrieve` incluye: `vector_backend=qdrant`, `instance_id`,
`qdrant_version`, `embedding_model`, `embedding_dim`, `collection_alias`, `generation`,
`public_alias`, `public_generation`, `score_metric=cosine`, `error_code` (nulo en éxito) y los campos
previos (`hits`, `status`, `origin_counts`). No contiene texto documental ni rutas locales.

En fallo, el paso registra `error_code` con el código clasificado.

## Reinicio y disponibilidad (embebido)

- Cierre y reapertura del cliente: el alias, el conteo y los resultados se conservan.
- Puerto cerrado: `qdrant_unavailable`.
- Marcador copiado a otra ruta: `instance_namespace_mismatch`.
- Ruta de chat con Qdrant caído: HTTP 503 y mensaje «El índice documental no está disponible.»; sin
  llamada al generador.

## Qualys

La importación sintética confirmada no crea documentos, fragmentos ni puntos Qdrant; los conteos antes
y después coinciden y el número de colecciones no cambia. La regresión documental de 002 sigue pasando.

## Servidor real + EmbeddingGemma

Instancia `cut3-smoke`, storage temporal, Qdrant 1.20.0 y `embeddinggemma` (768).

```text
rebuild 1: completed  public(2), case A(1), case B(1)
rebuild 2: completed  public(2), case A(1), case B(1)
search caso A: origenes public_corpus + case_evidence; v1 superada excluida; caso B excluido
cita historica v1: valid
config mismatch: instance_namespace_mismatch
servidor detenido: qdrant_unavailable
reinicio (down/up): conteo conservado (2) y busqueda con 3 resultados
```

El servicio se detuvo con `make qdrant-down` (sin `-v`); el volumen se conservó. No se modificó
`storage/` del usuario ni `storage/demo`, ni se borraron datos de Chroma.

## Revisión visual (Playwright MCP)

La página de ejecución renderiza `step.detail` como JSON; al añadirse campos de índice, se validó con
Playwright MCP. El detalle expandido muestra `vector_backend`, `qdrant_version`, alias, generación y
`score_metric`. Captura: `run-detail.png`.

Los mensajes de error no cambiaron de plantilla; su texto se comprueba en las pruebas de contrato.

## Limitaciones

- Caso sin documentos privados: `case_index_unavailable` hasta T054–T059.
- Sin calibración de umbral.
- Colecciones de smokes propios permanecen en el volumen local de Qdrant.
