# Contract: Index evidence

**Scope**: evidencia de qué índice atendió una ejecución y resultado de reconstrucción. No
implementa código.

## Run evidence

El paso `retrieve` de `RunStep.detail_json` puede incluir:

| Campo | Tipo | Significado |
|---|---|---|
| `vector_backend` | string | `qdrant` |
| `instance_id` | string | Namespace de instancia |
| `qdrant_version` | string | Versión reportada por el servidor, esperada `1.20.0` |
| `collection_alias` | string | Alias activo usado por el alcance |
| `generation` | string | Generación validada detrás del alias |
| `score_metric` | string | `cosine` |
| `hits` | integer | Fragmentos devueltos |
| `status` | string | `ok`, `empty` o estado de fallo del paso |
| `error_code` | string (opcional) | Código clasificado cuando el paso falla: `qdrant_unavailable`, `case_index_unavailable`, `public_index_unavailable` o `instance_namespace_mismatch` |

No se guardan rutas locales, secretos, texto completo de documentos ni payloads de Qualys. El código
de error se conserva tal cual; no se sustituye por `internal_error`.

## Rebuild evidence

El comando de reconstrucción escribe un reporte JSON local con:

- fecha de inicio/fin;
- versión de Qdrant y cliente;
- modelo y dimensión de embeddings;
- alcance (público/caso), generación y alias;
- fragmentos esperados, indexados, faltantes y extra;
- estado `completed`, `partial` o `failed`;
- error clasificado y mensaje comprensible.

El reporte es operativo; no es fuente de verdad ni se guarda en SQLite.

## No new tables

No se crean tablas SQLite para el estado del índice. Se usan:

- Qdrant: colecciones, aliases y puntos;
- SQLite: `RunStep.detail_json` para evidencia de ejecución;
- archivo JSON local para el reporte de reconstrucción.

Si una implementación futura necesita persistencia adicional, debe justificarla y usar una
migración aditiva; no se crea por costumbre.
