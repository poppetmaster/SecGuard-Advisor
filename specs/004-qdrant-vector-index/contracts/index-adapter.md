# Contract: Qdrant index adapter

**Scope**: reemplazo del adaptador de índice documental. No implementa código.

## Interface

El adaptador expone el mismo contrato de dominio que el índice actual, sin exponer Qdrant al
dominio:

```text
upsert(scope, model, dimension, chunks)
delete_ids(scope, model, dimension, ids)
delete_version(scope, model, dimension, version_id)
count(scope, model, dimension)
query(scope, model, dimension, vector, top_k)
```

`scope` distingue `public` y `case(case_id)`. El adaptador resuelve el alias activo del alcance;
nunca consulta una generación parcial.

## Semantics

- **Instance namespace:** toda operación usa `SECGUARD_INSTANCE_ID`; el adaptador rechaza un ID
  ausente, inválido o incompatible con el marcador de storage. No genera IDs por arranque.
- **Model/dimension:** deben coincidir con la generación y con `DocumentVersion`/`DocumentChunk`.
  Una discrepancia es un error explícito; no se mezclan vectores.
- **Point ID:** UUIDv5 determinista del `chunk_id`; el payload conserva `instance_id`, `chunk_id` y
  metadatos de procedencia.
- **Payload:** metadatos de procedencia; no texto completo. El texto se resuelve en SQLite.
- **Score:** Qdrant devuelve similitud coseno (mayor es mejor). El adaptador no debe devolver un
  “distance” ambiguo; la aplicación aplica el umbral calibrado.
- **Alias:** la consulta usa el alias `secguard__<instance>__...__active`. Un alias ausente con
  datos esperados produce un error de índice no disponible.
- **Upsert:** idempotente por point ID; no duplica si se repite el mismo `chunk_id`.
- **First document:** si el caso no tiene alias, el adaptador crea la generación/alias inicial solo
  después de validar el primer documento. Una versión fallida no recibe alias.
- **Delete:** solo afecta la generación/alcance indicado. No borra colecciones ajenas ni datos
  Chroma.
- **Errores:** conexión, timeout, versión incompatible, dimensión incompatible, namespace
  incompatible, alias ausente y payload inválido se clasifican y se reportan; no hay fallback a
  Chroma. Los códigos y estados son obligatorios y se registran en `web/errors.py`:
  `qdrant_unavailable` (503), `case_index_unavailable` (503), `public_index_unavailable` (503),
  `instance_namespace_mismatch` (503), `reconstruction_in_progress` (409) e
  `ingestion_in_progress` (409). Un código debe conservarse en la respuesta y en la evidencia; no
  se degrada a `internal_error`.

## Out of scope

- Selección de backend.
- Escritura dual.
- Exportación de vectores desde Chroma.
- Borrado de archivos o colecciones ajenas.
- Cambio de embeddings.
