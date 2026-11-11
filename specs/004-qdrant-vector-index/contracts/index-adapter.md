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

- **Model/dimension:** deben coincidir con la generación y con `DocumentVersion`/`DocumentChunk`.
  Una discrepancia es un error explícito; no se mezclan vectores.
- **Point ID:** UUIDv5 determinista del `chunk_id`; el payload conserva `chunk_id`.
- **Payload:** metadatos de procedencia; no texto completo. El texto se resuelve en SQLite.
- **Score:** Qdrant devuelve similitud coseno (mayor es mejor). El adaptador no debe devolver un
  “distance” ambiguo; la aplicación aplica el umbral calibrado.
- **Alias:** la consulta usa el alias `...__active`. Un alias ausente o inválido produce un error de
  índice no disponible.
- **Upsert:** idempotente por point ID; no duplica si se repite el mismo `chunk_id`.
- **Delete:** solo afecta la generación/alcance indicado. No borra colecciones ajenas ni datos
  Chroma.
- **Errores:** conexión, timeout, versión incompatible, dimensión incompatible, alias ausente y
  payload inválido se clasifican y se reportan; no hay fallback a Chroma.

## Out of scope

- Selección de backend.
- Escritura dual.
- Exportación de vectores desde Chroma.
- Borrado de archivos o colecciones ajenas.
- Cambio de embeddings.
