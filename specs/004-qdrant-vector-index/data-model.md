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
  "instance_id": "presentacion-2026",
  "qdrant_version": "1.20.0",
  "collection_alias": "secguard__presentacion-2026__case__<case_id>__embeddinggemma__768__active",
  "generation": "20261111T...Z",
  "score_metric": "cosine",
  "public_alias": "secguard__presentacion-2026__public__embeddinggemma__768__active",
  "public_generation": "20261111T...Z"
}
```

La identidad del índice se captura al ejecutar la consulta concreta; no se re-resuelve después. Si la
identidad no está disponible, no se inventa.

Ante un fallo de índice, el mismo paso registra `status` distinto de `ok` y `error_code` con el código
clasificado (`qdrant_unavailable`, `case_index_unavailable`, `public_index_unavailable` o
`instance_namespace_mismatch`).

No se guardan rutas locales, secretos ni texto de documentos.

## Identidad de instancia

### Configuración persistente

`SECGUARD_INSTANCE_ID` es un slug estable y opaco, obligatorio para Qdrant. Se configura en
entorno/`.env` y no se genera en cada arranque. No contiene rutas privadas.

`<SECGUARD_STORAGE_DIR>/qdrant-control/instances/<instance_id>.json` conserva:

```json
{
  "instance_id": "presentacion-2026",
  "storage_fingerprint": "<sha256 de la ruta canónica del almacenamiento + instance_id>",
  "schema_version": 1,
  "created_at": "2026-11-11T...Z"
}
```

La ruta del marcador es relativa a `SECGUARD_STORAGE_DIR`. El fingerprint se calcula sobre la ruta
canónica del almacenamiento combinada con el `instance_id`; **no** depende del contenido, tamaño,
fecha de modificación ni hash de los archivos SQLite, de los documentos ni del propio marcador,
porque esos datos cambian durante el uso normal. No se expone la ruta legible.

Registro y no adopción:

| Situación | Comportamiento |
|---|---|
| Marcador ausente y sin colecciones/alias de esa instancia en el servidor | Se crea en el primer uso, aunque el servidor ya contenga otras instancias. |
| Marcador ausente pero con colecciones/alias de esa instancia ya presentes | `instance_namespace_mismatch`; no se escribe ni se adopta el namespace. |
| Marcador presente con `instance_id` o fingerprint distintos | `instance_namespace_mismatch`; no se escribe ni se cambia alias. |
| Marcador presente y coincidente | Se continúa. |

### Namespace aplicado

```text
secguard__<instance_id>__public__...
secguard__<instance_id>__case__<case_id>__...
<SECGUARD_STORAGE_DIR>/qdrant-control/locks/<instance_id>.lock
<SECGUARD_STORAGE_DIR>/qdrant-control/reports/<instance_id>/
```

El volumen de datos del servidor Qdrant (`./storage/qdrant` → `/qdrant/storage`) contiene solo
archivos del servidor. Marcadores, locks y reportes viven en `qdrant-control/`, fuera de ese volumen.

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
8. Si el commit en SQLite falla después de escribir puntos o publicar el alias, la versión queda no
   disponible; el alias puede existir sobre puntos que no son resolubles hasta que SQLite marque la
   versión disponible. El reintento vuelve a indexar la misma versión, limpia por `version_id` y
   reutiliza los UUIDv5 deterministas, de modo que converge sin duplicados. No se publica un alias
   nuevo ni se declara éxito a partir de puntos sin versión disponible.
9. Documentos posteriores usan el alias existente; no crean una generación por documento.

**No hay atomicidad entre Qdrant y SQLite.** SQLite es la única autoridad sobre disponibilidad: una
consulta excluye toda versión que no esté `available` o que no sea la vigente, aunque sus puntos
existan en Qdrant.

La reconstrucción inicial es distinta: crea una generación nueva para todos los documentos
existentes y cambia el alias.

## Bloqueo de mantenimiento

`<SECGUARD_STORAGE_DIR>/qdrant-control/locks/<instance_id>.lock` es un lock de archivo exclusivo,
compartido por la aplicación, la ingesta del corpus y el comando de reconstrucción. Se adquiere antes
de escribir el índice y se libera en `finally`. El sistema operativo lo libera si el proceso muere.

### Registro de propietario

Mientras posee el lock, el proceso escribe en el mismo archivo de lock:

```json
{
  "operation": "ingestion|rebuild",
  "attempt_id": "<id opaco del intento>",
  "pid": 12345,
  "started_at": "2026-11-11T...Z"
}
```

Reglas:

- El registro se escribe solo después de adquirir el lock y se considera inválido al liberarlo.
- La autoridad de actividad es el bloqueo real. Si el lock puede adquirirse, el registro está
  obsoleto y se ignora, aunque el archivo conserve contenido de un proceso muerto.
- Un registro obsoleto no demuestra actividad ni éxito.
- El estado distingue ingesta activa (lock con `operation=ingestion`), reconstrucción activa (lock con
  `operation=rebuild`) y último resultado terminal (`latest.json`).
- El registro se escribe en el mismo archivo bloqueado con `flock`, válido en macOS y Linux; Windows
  queda fuera del objetivo declarado.
- No se crea tabla SQLite ni pantalla administrativa.

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

No se crea una tabla. El comando de reconstrucción es la interfaz operativa de estado y avance, y
produce un reporte JSON local con:

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
      "alias": "secguard__<instance_id>__...__active",
      "expected_chunks": 0,
      "indexed_chunks": 0,
      "missing_chunks": 0,
      "extra_chunks": 0,
      "previous_missing_chunks": 0,
      "previous_extra_chunks": 0,
      "skipped_chunks": 0,
      "status": "completed|partial|failed",
      "error": null
    }
  ]
}
```

`missing_chunks`, `extra_chunks` y `skipped_chunks` describen la **generación candidata** y deciden
su publicación. `previous_missing_chunks` y `previous_extra_chunks` describen la generación activa
anterior y son diagnóstico: un índice anterior desactualizado no impide publicar una candidata válida.
Los huérfanos se siguen reportando y nunca se resuelven como cita.

El reporte es operativo, no fuente de verdad. No se escribe en SQLite. Se guarda en
`<SECGUARD_STORAGE_DIR>/qdrant-control/reports/<instance_id>/` con un archivo por ejecución y un
`latest.json` con el último resultado terminal.

### Cinco estados observables

| Estado | De dónde se obtiene | Interpretación |
|---|---|---|
| `not_started` | No hay `latest.json` y el lock no está tomado por una reconstrucción | No hay reconstrucción registrada. No implica fallo: el alias existente sigue siendo el vigente. |
| `in_progress` | Lock tomado por un proceso vivo cuyo registro declara `operation=rebuild` | Reconstrucción en curso. El `latest.json` anterior describe el intento anterior, no éste. No es éxito. |
| `completed` | `status` del último reporte terminal | Todos los alcances declarados se validaron. |
| `partial` | `status` del último reporte terminal | Algún alcance quedó incompleto; un alcance validado puede tener alias propio y el reporte global no declara la reconstrucción completa. |
| `failed` | `status` del último reporte terminal | El intento terminó con error; el alias anterior se conserva. |

Un lock con `operation=ingestion` indica ingesta activa, no reconstrucción en curso: se muestra el
último resultado terminal. Un lock activo no se interpreta como éxito y un reporte ausente no se
interpreta como fallo. Un registro residual con el lock libre se ignora.

### Consulta de estado de solo lectura

`uv run python scripts/rebuild_qdrant.py --status` devuelve un objeto con `state`, el propietario del
lock cuando está activo y el último resultado terminal. El resolvedor único vive en
`retrieval/status.py`: la CLI y el reporte lo consumen y no reimplementan el sondeo del lock, la
lectura del propietario ni la interpretación del reporte.

```json
{
  "state": "<not_started|ingestion_in_progress|rebuild_in_progress|completed|partial|failed>",
  "lock_owner": null,
  "last_terminal": null
}
```

`lock_owner` contiene `{operation, attempt_id, pid, started_at}` solo cuando hay un lock activo.
`last_terminal` contiene `{status, finished_at, report}` cuando existe un reporte terminal.

| Situación | `state` |
|---|---|
| Sin lock activo y sin `latest.json` | `not_started`; `last_terminal` es `null`; salida 0 |
| Lock tomado por un proceso vivo con `operation=ingestion` | `ingestion_in_progress` |
| Lock tomado por un proceso vivo con `operation=rebuild` | `rebuild_in_progress` |
| Lock libre y último reporte terminal `completed` | `completed` |
| Lock libre y último reporte terminal `partial` | `partial` |
| Lock libre y último reporte terminal `failed` | `failed` |

La consulta no inicia reconstrucciones, no genera embeddings, no crea colecciones, no registra
instancias, no escribe archivos y no cambia aliases. Si el archivo de lock no existe, no se crea.

Casos de error de la consulta, todos con salida 2, mensaje en `stderr` y el mismo objeto
(`state: null`, `last_terminal: null`):

| Situación | `error.code` |
|---|---|
| Reporte terminal ilegible | `status_report_unreadable` |
| Configuración de instancia ausente o inválida | `instance_configuration_invalid` |
| Archivo de lock existente pero ilegible, o lock tomado con registro de propietario ausente o corrupto | `lock_unreadable` |

En los tres casos no se presenta el resultado como `not_started`, no se afirma que no existe una
operación activa, no se crea marcador, lock, directorio ni otro archivo, y no se repara, borra ni
sobrescribe información.

## Puntos huérfanos

Un punto Qdrant cuyo `payload.chunk_id` no existe en SQLite (o cuya versión no existe) es una
**discrepancia**: se cuenta en `extra_chunks`, se reporta y nunca se resuelve como cita ni se
devuelve como resultado.

## Invariantes

1. SQLite conserva documentos, versiones, fragmentos, citas y procedencia.
2. Qdrant no se usa para reconstruir SQLite.
3. Un alias activo solo apunta a una generación validada.
4. Un índice parcial no se presenta como listo.
5. Un punto Qdrant debe resolver a un `chunk_id` existente en SQLite; si no, se reporta como
   discrepancia y no se resuelve como cita.
6. Un fragmento privado de un caso no se recupera desde otro caso.
7. El corpus público es compartido y conserva su procedencia.
8. Los registros Qualys no se convierten en puntos, documentos ni citas.
9. Las citas históricas no dependen de que la versión esté indexada.
10. Los archivos y datos Chroma no se borran en 004.
11. No existe atomicidad entre Qdrant y SQLite: SQLite decide la disponibilidad y el reintento
    converge sin duplicados.
12. El registro de propietario del lock no demuestra actividad si el lock está libre; la autoridad es
    el bloqueo real.

## Sin cambios de esquema

No se requieren tablas, columnas ni migraciones nuevas para 004. Si la implementación futura
necesita persistir un estado operativo adicional, deberá justificarlo y usar una migración aditiva;
no se crea por costumbre.
