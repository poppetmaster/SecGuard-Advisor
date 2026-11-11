# Data Model: Migración del índice documental a Qdrant

**Fecha**: 2026-11-11  
**Alcance**: modelo conceptual y correspondencia con las estructuras existentes. No crea tablas,
migraciones ni datos.

## Principios

- SQLite sigue siendo la fuente de verdad.
- Qdrant es un índice derivado, reconstruible y no autoritativo.
- No se crean tablas SQLite nuevas. La persistencia adicional es Qdrant (colecciones, aliases,
  puntos) y un reporte JSON operativo de reconstrucción.
- Los documentos, versiones, fragmentos, citas, conversaciones, revisiones, checkpoints, Qualys y
  evidencia se conservan sin recrear SQLite.
- Los vectores no están en SQLite: se regeneran con el modelo local vigente.

## Entidades existentes que se conservan

### Document

Representa un documento del caso o del corpus público.

| Campo relevante | Uso en 004 |
|---|---|
| `id` | Identificador estable; se copia al payload Qdrant. |
| `case_id` | `NULL` para corpus público; identifica el caso para aislamiento. |
| `origin` | `public_corpus` o `case_evidence`; se copia al payload. |
| `title` | Se copia como `document_title` para evidencia; el texto se resuelve desde SQLite. |
| `current_version_id` | Determina la versión vigente que se indexa. |
| `status`/metadatos | Sin cambios. |

### DocumentVersion

Representa una versión de un documento. Las versiones superadas permanecen en SQLite para citas
históricas, pero no se indexan para búsquedas nuevas.

| Campo relevante | Uso en 004 |
|---|---|
| `id` | Se copia al payload. |
| `document_id` | Se copia al payload. |
| `status` | Solo `available` se indexa. |
| `declared_version` | Se copia al payload para evidencia. |
| `embedding_model`, `embedding_dim` | Deben coincidir con el modelo/dimensión de la reconstrucción. |

### DocumentChunk

Unidad indexable y fuente de verdad del texto y localizador.

| Campo | Uso en 004 |
|---|---|
| `id` (`chunk_id`) | Identificador autoritativo; se copia al payload. El point ID Qdrant es UUIDv5. |
| `version_id` | Se copia al payload. |
| `chunk_index` | Se copia al payload; orden dentro de la versión. |
| `page_start`, `page_end` | Se copian al payload. |
| `section` | Se copia al payload. |
| `char_start`, `char_end` | No se copian; el texto se resuelve desde SQLite. |
| `text` | No se copia al payload; se resuelve desde SQLite. |
| `text_sha256` | No se copia; sirve para verificar integridad local si se necesita. |
| `token_count` | No se copia; se conserva en SQLite. |
| `token_count_source` | No se copia. |
| `embedding_model`, `embedding_dim` | Se copian; deben coincidir con la generación. |
| `index_status` | Se conserva como estado histórico; no se usa para decidir el estado del índice Qdrant. |
| `locator` | Se copia al payload; resuelve la cita. |

### RunStep

Evidencia existente de un paso del turno. No se crea una tabla nueva.

El paso `retrieve` puede guardar en `detail_json`:

```json
{
  "hits": 6,
  "status": "ok",
  "vector_backend": "qdrant",
  "qdrant_version": "1.20.0",
  "collection_alias": "secguard__case__<case_id>__embeddinggemma__768__active",
  "generation": "20261111T...Z",
  "score_metric": "cosine"
}
```

No se guardan rutas locales, secretos ni texto de documentos.

## Identidad de instancia

### Configuración persistente

`SECGUARD_INSTANCE_ID` es un slug estable y opaco, obligatorio para Qdrant. Se configura en
entorno/`.env` y no se genera en cada arranque. No contiene rutas privadas.

`storage/qdrant/instances/<instance_id>.json` conserva:

```json
{
  "instance_id": "presentacion-2026",
  "storage_fingerprint": "<sha256 del storage root canónico>",
  "schema_version": 1,
  "created_at": "2026-11-11T...Z"
}
```

El fingerprint es un hash, no una ruta legible. Si el marcador no existe y Qdrant está vacío, se
crea en el primer uso. Si no coincide con el ID o el storage actual, se falla con
`instance_namespace_mismatch`; no se escribe ni se cambia un alias. Esto distingue una copia de
SQLite/storage en otra ruta aunque conserve el mismo contenido.

### Namespace aplicado

```text
secguard__<instance_id>__public__...
secguard__<instance_id>__case__<case_id>__...
storage/qdrant/locks/<instance_id>.lock
storage/qdrant/reports/<instance_id>/
```

No se crea tabla SQLite para la instancia.

## Entidades nuevas en Qdrant

### Colección física

Una colección por alcance y generación:

```text
secguard__<instance_id>__public__<model-slug>__<dim>__g<UTC>
secguard__<instance_id>__case__<case_id>__<model-slug>__<dim>__g<UTC>
```

Contiene puntos con vector y payload. No es fuente de verdad. Se crea durante la reconstrucción o
en el primer documento validado de un caso. Se conserva la generación anterior para recuperación.

### Alias activo

Alias estable por alcance:

```text
secguard__<instance_id>__public__<model-slug>__<dim>__active
secguard__<instance_id>__case__<case_id>__<model-slug>__<dim>__active
```

La consulta usa el alias. El alias cambia solo después de validar la generación. Un alias ausente
con datos esperados produce un error explícito de índice no disponible; no se consulta una
generación parcial. Un alcance realmente vacío no requiere alias.

### Punto Qdrant

| Campo | Tipo | Origen |
|---|---|---|
| point ID | UUID | UUIDv5 determinista de `chunk_id` |
| vector | float[768] | `embeddinggemma` local |
| `instance_id` | keyword | Namespace de la instancia |
| `chunk_id` | keyword | `DocumentChunk.id` |
| `document_id` | keyword | `Document.id` |
| `version_id` | keyword | `DocumentVersion.id` |
| `origin` | keyword | `public_corpus`/`case_evidence` |
| `source_id` | keyword/null | fuente pública |
| `page_start`, `page_end` | integer/null | `DocumentChunk` |
| `section` | text/null | `DocumentChunk` |
| `locator` | keyword | `DocumentChunk.locator` |
| `document_title` | text | `Document.title` |
| `declared_version` | text/null | `DocumentVersion.declared_version` |
| `chunk_index` | integer | `DocumentChunk.chunk_index` |
| `embedding_model` | keyword | modelo local |
| `embedding_dim` | integer | 768 |

El texto y los datos completos de la cita se resuelven desde SQLite por `chunk_id`.

## Correspondencia e idempotencia

```text
DocumentChunk.id (32 hex)
  → UUIDv5(namespace=SecGuard, name="chunk:" + chunk_id)
  → Qdrant point ID
  → payload.chunk_id = DocumentChunk.id
  → SQLite resolve(citation/fragment)
```

- La misma entrada produce siempre el mismo point ID.
- Repetir la reconstrucción en una generación nueva no duplica puntos.
- Un `chunk_id` ausente en SQLite no se inventa; un punto huérfano se reporta y no se resuelve.
- Un punto con payload incompatible se reporta; no se mezcla con la generación válida.

## Ciclo de vida del primer documento

Un caso sin colección/alias no se considera un error. La ingesta crea el índice mínimo:

1. Documento/versión/fragmentos se persisten en SQLite; versión no disponible.
2. Se generan embeddings y puntos.
3. Se adquiere el lock de escritura de la instancia.
4. Si no existe alias del caso, se crea una generación inicial y se suben los puntos validados.
5. Se verifica que los `chunk_id` de la versión estén en Qdrant.
6. Se publica el alias del caso y se marca la versión `available`.
7. Si extracción, embedding o escritura fallan, la versión queda `failed`/no disponible y no se
   publica alias nuevo. El reintento limpia por `version_id` y repite el flujo.
8. Documentos posteriores usan el alias existente; no crean una generación por documento.

La reconstrucción inicial es distinta: crea una generación nueva para todos los documentos
existentes y cambia el alias.

## Bloqueo de mantenimiento

`storage/qdrant/locks/<instance_id>.lock` es un lock de archivo exclusivo, compartido por la
aplicación y el comando de reconstrucción. Se adquiere antes de escribir el índice y se libera en
`finally`. El sistema operativo lo libera si el proceso muere.

- Ingesta con lock de reconstrucción: `reconstruction_in_progress`, sin escritura.
- Reconstrucción con lock de ingesta: `ingestion_in_progress`, sin espera indefinida.
- Consultas: no toman el lock; usan el alias anterior.
- Instancias distintas usan locks distintos.

## Alcance vacío frente a índice ausente

| Estado | Resultado |
|---|---|
| Caso sin documentos privados disponibles | Se omite el alcance privado; se consulta el público. |
| Caso con documentos esperados pero sin alias | `case_index_unavailable`; no se responde solo con público. |
| Público con documentos esperados pero sin alias | `public_index_unavailable`; no se declara falta de evidencia. |
| Público no configurado o vacío | Se omite; el caso puede continuar. |
| Qdrant inaccesible | `qdrant_unavailable`; sin Chroma. |
| Alias presente sin resultados | `empty` normal; no se inventa cita. |

“Esperado” se calcula desde SQLite, no desde la ausencia de alias.

## Selección de versiones

- **Búsquedas nuevas:** solo fragmentos de `Document.current_version_id` con
  `DocumentVersion.status == available`.
- **Citas históricas:** cualquier versión persistida se resuelve desde SQLite por `chunk_id` y
  `version_id`, aunque no esté indexada en Qdrant.
- **Versiones superadas:** no se indexan para búsquedas nuevas; no reaparecen por defecto.
- **Documentos no disponibles:** no se indexan; sus citas históricas siguen resolviendo si el
  fragmento persistido existe.

## Estado de reconstrucción

No se crea una tabla. El comando de reconstrucción produce un reporte JSON local con:

```json
{
  "started_at": "2026-11-11T...Z",
  "finished_at": "2026-11-11T...Z",
  "status": "completed|partial|failed",
  "backend": "qdrant",
  "qdrant_version": "1.20.0",
  "embedding_model": "embeddinggemma",
  "embedding_dim": 768,
  "scopes": [
    {
      "scope": "public|case",
      "case_id": "<id o null>",
      "generation": "20261111T...Z",
      "alias": "secguard__...__active",
      "expected_chunks": 0,
      "indexed_chunks": 0,
      "missing_chunks": 0,
      "extra_chunks": 0,
      "status": "completed|partial|failed",
      "error": null
    }
  ]
}
```

El reporte es operativo, no fuente de verdad. No se escribe en SQLite.

## Invariantes

1. SQLite conserva documentos, versiones, fragmentos, citas y procedencia.
2. Qdrant no se usa para reconstruir SQLite.
3. Un alias activo solo apunta a una generación validada.
4. Un índice parcial no se presenta como listo.
5. Un punto Qdrant siempre resuelve a un `chunk_id` existente en SQLite.
6. Un fragmento privado de un caso no se recupera desde otro caso.
7. El corpus público es compartido y conserva su procedencia.
8. Los registros Qualys no se convierten en puntos, documentos ni citas.
9. Las citas históricas no dependen de que la versión esté indexada.
10. Los archivos y datos Chroma no se borran en 004.

## Sin cambios de esquema

No se requieren tablas, columnas ni migraciones nuevas para 004. Si la implementación futura
necesita persistir un estado operativo adicional, deberá justificarlo y usar una migración aditiva;
no se crea por costumbre.
