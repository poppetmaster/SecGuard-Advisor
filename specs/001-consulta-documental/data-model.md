# Modelo de datos — Funcionalidad 001

Convenciones: identificadores `TEXT` con UUID4 hexadecimal (32 caracteres); fechas en ISO-8601
UTC como `TEXT`; booleanos como `INTEGER` 0/1; JSON validado con pydantic antes de escribirse.
SQLite con `foreign_keys=ON`, `journal_mode=WAL` y `busy_timeout`.

**16 tablas**, todas justificadas en `plan.md` § Auditoría de persistencia. No hay tablas para
funciones de incrementos posteriores.

## 1. Diagrama de relaciones

```text
cases 1──N assets
cases 1──N documents (solo evidencia de caso)
documents 1──N document_versions 1──N document_chunks
document_versions 1──N ingestion_jobs
cases 1──1 conversations 1──N messages 1──N message_citations
message_citations N──1 document_chunks
cases 1──N runs 1──N run_steps
runs 1──N run_sources N──1 document_chunks
runs 1──N run_tool_calls
synthetic_datasets 1──N findings N──1 assets
findings 1──N finding_cves

externo: data/corpus/manifest.json ──(source_id)──> documents (corpus público)
```

El manifiesto del corpus es la fuente de bibliografía y licencias; `documents.source_id` lo
referencia y se valida al arrancar. No se duplica en una tabla.

## 2. Tablas

### 2.1 `cases`

| Campo | Tipo | Restricción |
|---|---|---|
| `id` | TEXT | PK |
| `title` | TEXT | NOT NULL, `length(trim(title)) > 0` |
| `description` | TEXT | NULL |
| `ai_application` | TEXT | NULL |
| `data_processed` | TEXT | NULL |
| `restrictions` | TEXT | NULL |
| `context_is_synthetic` | INTEGER | NOT NULL DEFAULT 1, CHECK IN (0,1) |
| `synthetic_notice` | TEXT | NOT NULL |
| `created_at` | TEXT | NOT NULL |
| `updated_at` | TEXT | NOT NULL |

Campos nulos significan «desconocido». El servicio nunca los completa; la interfaz los muestra
como desconocidos.

### 2.2 `assets`

| Campo | Tipo | Restricción |
|---|---|---|
| `id` | TEXT | PK |
| `case_id` | TEXT | NOT NULL, FK `cases(id)` ON DELETE CASCADE |
| `name` | TEXT | NOT NULL |
| `description` | TEXT | NULL |
| `created_at` | TEXT | NOT NULL |

`UNIQUE(case_id, name)`.

### 2.3 `documents`

| Campo | Tipo | Restricción |
|---|---|---|
| `id` | TEXT | PK |
| `scope_key` | TEXT | NOT NULL (`case:<id>` o `public:<source_id>`) |
| `case_id` | TEXT | NULL, FK `cases(id)` ON DELETE CASCADE |
| `origin` | TEXT | NOT NULL, CHECK IN (`case_evidence`,`public_corpus`) |
| `source_id` | TEXT | NULL, identificador del manifiesto; validado al arrancar |
| `title` | TEXT | NOT NULL |
| `current_version_id` | TEXT | NULL, sin FK física (evita un ciclo); se valida en el servicio |
| `created_at` | TEXT | NOT NULL |

```sql
CHECK (
  (origin = 'case_evidence' AND case_id IS NOT NULL AND source_id IS NULL)
  OR
  (origin = 'public_corpus' AND case_id IS NULL AND source_id IS NOT NULL)
)
```

Esta restricción separa físicamente el corpus público de la evidencia privada. Una fuente pública
no tiene caso y es accesible desde todos; una evidencia privada tiene exactamente un caso.

### 2.4 `document_versions`

| Campo | Tipo | Restricción |
|---|---|---|
| `id` | TEXT | PK |
| `document_id` | TEXT | NOT NULL, FK `documents(id)` ON DELETE CASCADE |
| `scope_key` | TEXT | NOT NULL (desnormalizado para la unicidad) |
| `version_number` | INTEGER | NOT NULL, ≥ 1 |
| `original_filename` | TEXT | NOT NULL |
| `content_type` | TEXT | NOT NULL |
| `bytes` | INTEGER | NOT NULL, > 0 |
| `sha256` | TEXT | NOT NULL, 64 hex |
| `declared_version` | TEXT | NULL |
| `declared_date` | TEXT | NULL |
| `status` | TEXT | NOT NULL, CHECK IN (`pending`,`processing`,`available`,`no_usable_text`,`failed`,`superseded`) |
| `error_code` | TEXT | NULL |
| `error_message` | TEXT | NULL |
| `page_count` | INTEGER | NULL |
| `readable_pages` | INTEGER | NULL |
| `unreadable_pages` | TEXT | NULL, JSON array de enteros |
| `extraction_version` | TEXT | NOT NULL |
| `normalization_version` | TEXT | NOT NULL |
| `chunking_version` | TEXT | NOT NULL |
| `embedding_model` | TEXT | NULL |
| `embedding_dim` | INTEGER | NULL |
| `retrieved_at` | TEXT | NULL |
| `license` | TEXT | NULL |
| `created_at` | TEXT | NOT NULL |
| `superseded_at` | TEXT | NULL |

`UNIQUE(document_id, version_number)`
`UNIQUE(scope_key, sha256)` — impone la deduplicación por contenido dentro del mismo espacio.
`INDEX(scope_key, status)`

### 2.5 `document_chunks`

| Campo | Tipo | Restricción |
|---|---|---|
| `id` | TEXT | PK |
| `version_id` | TEXT | NOT NULL, FK `document_versions(id)` ON DELETE CASCADE |
| `chunk_index` | INTEGER | NOT NULL, ≥ 0 |
| `page_start` | INTEGER | NULL |
| `page_end` | INTEGER | NULL |
| `section` | TEXT | NULL |
| `char_start` | INTEGER | NOT NULL |
| `char_end` | INTEGER | NOT NULL |
| `text` | TEXT | NOT NULL |
| `text_sha256` | TEXT | NOT NULL |
| `token_count` | INTEGER | NOT NULL, > 0 |
| `token_count_source` | TEXT | NOT NULL, valor `ollama_prompt_eval_count_single` |
| `embedding_model` | TEXT | NOT NULL |
| `embedding_dim` | INTEGER | NOT NULL |
| `index_status` | TEXT | NOT NULL, CHECK IN (`pending`,`indexed`,`failed`) |
| `index_error` | TEXT | NULL |
| `locator` | TEXT | NOT NULL |
| `created_at` | TEXT | NOT NULL |

`UNIQUE(version_id, chunk_index)`, `INDEX(version_id, index_status)`.

`token_count` se llena **por fragmento**, con una petición de un solo texto a `/api/embed`. El
conteo agregado de una petición por lotes no se usa como validación individual.

### 2.6 `ingestion_jobs`

| Campo | Tipo | Restricción |
|---|---|---|
| `id` | TEXT | PK |
| `case_id` | TEXT | NULL, FK `cases(id)` |
| `version_id` | TEXT | NOT NULL, FK `document_versions(id)` ON DELETE CASCADE |
| `status` | TEXT | NOT NULL, CHECK IN (`queued`,`running`,`succeeded`,`failed`,`interrupted`) |
| `attempts` | INTEGER | NOT NULL DEFAULT 0 |
| `error_code` | TEXT | NULL |
| `error_message` | TEXT | NULL |
| `created_at` | TEXT | NOT NULL |
| `started_at` | TEXT | NULL |
| `finished_at` | TEXT | NULL |
| `heartbeat_at` | TEXT | NULL |

`INDEX(status)`, `INDEX(version_id)`.

### 2.7 `conversations`

| Campo | Tipo | Restricción |
|---|---|---|
| `id` | TEXT | PK |
| `case_id` | TEXT | NOT NULL, UNIQUE, FK `cases(id)` ON DELETE CASCADE |
| `thread_id` | TEXT | NOT NULL, UNIQUE (igual a `id`) |
| `created_at` | TEXT | NOT NULL |
| `updated_at` | TEXT | NOT NULL |

### 2.8 `messages`

| Campo | Tipo | Restricción |
|---|---|---|
| `id` | TEXT | PK |
| `conversation_id` | TEXT | NOT NULL, FK `conversations(id)` ON DELETE CASCADE |
| `seq` | INTEGER | NOT NULL, ≥ 1 |
| `role` | TEXT | NOT NULL, CHECK IN (`user`,`assistant`) |
| `content` | TEXT | NOT NULL |
| `status` | TEXT | NOT NULL, CHECK IN (`complete`,`error`) |
| `run_id` | TEXT | NULL, sin FK física (evita un ciclo); se valida en el servicio |
| `created_at` | TEXT | NOT NULL |

`UNIQUE(conversation_id, seq)`.

El mensaje de usuario se crea una vez por turno. Los reintentos lo reutilizan y se distinguen por
`runs.attempt_no`; no se inserta un segundo mensaje de usuario.

### 2.9 `message_citations`

| Campo | Tipo | Restricción |
|---|---|---|
| `id` | TEXT | PK |
| `message_id` | TEXT | NOT NULL, FK `messages(id)` ON DELETE CASCADE |
| `chunk_id` | TEXT | NOT NULL, FK `document_chunks(id)` |
| `document_id` | TEXT | NOT NULL |
| `document_version_id` | TEXT | NOT NULL |
| `page` | INTEGER | NULL |
| `section` | TEXT | NULL |
| `quote` | TEXT | NOT NULL |
| `locator` | TEXT | NOT NULL |
| `check_status` | TEXT | NOT NULL, CHECK IN (`valid`,`rejected`) |
| `check_reason` | TEXT | NULL |
| `support_review_status` | TEXT | NOT NULL DEFAULT `unreviewed`, CHECK IN (`unreviewed`,`supported`,`not_supported`) |
| `support_reviewed_by` | TEXT | NULL |
| `support_reviewed_at` | TEXT | NULL |
| `support_review_note` | TEXT | NULL |
| `created_at` | TEXT | NOT NULL |

`INDEX(message_id)`. Las citas `rejected` no se muestran en la respuesta, pero se conservan para
auditoría. `check_status` es el control automático; `support_review_status` es la revisión humana y
es independiente.

```sql
CHECK (support_review_status = 'unreviewed'
       OR (support_reviewed_by IS NOT NULL AND support_reviewed_at IS NOT NULL))
```

`support_reviewed_by` se toma de `SECGUARD_REVIEWER_NAME`. Si la configuración está vacía, la
aplicación rechaza la revisión y no escribe la fila. Es una identidad local declarada, no
autenticación.

### 2.10 `runs`

| Campo | Tipo | Restricción |
|---|---|---|
| `id` | TEXT | PK |
| `case_id` | TEXT | NOT NULL, FK `cases(id)` |
| `conversation_id` | TEXT | NOT NULL, FK `conversations(id)` |
| `question_message_id` | TEXT | NULL, FK `messages(id)` |
| `answer_message_id` | TEXT | NULL, FK `messages(id)` |
| `kind` | TEXT | NOT NULL, CHECK IN (`chat`) |
| `attempt_no` | INTEGER | NOT NULL DEFAULT 1, ≥ 1 |
| `retry_of_run_id` | TEXT | NULL, FK `runs(id)`; intento que se reintenta |
| `status` | TEXT | NOT NULL, CHECK IN (`running`,`succeeded`,`failed`,`timeout`,`interrupted`) |
| `outcome` | TEXT | NULL, CHECK IN (`answered`,`insufficient_evidence`,`abstained_invalid_citations`,`error`) |
| `generator_model` | TEXT | NOT NULL |
| `generator_digest` | TEXT | NULL |
| `generator_num_ctx` | INTEGER | NOT NULL |
| `generator_temperature` | REAL | NOT NULL |
| `generator_seed` | INTEGER | NULL |
| `embedding_model` | TEXT | NOT NULL |
| `embedding_dim` | INTEGER | NOT NULL |
| `prompt_version` | TEXT | NOT NULL |
| `duration_ms` | INTEGER | NULL |
| `steps_count` | INTEGER | NOT NULL DEFAULT 0 |
| `tool_calls_count` | INTEGER | NOT NULL DEFAULT 0 |
| `error_code` | TEXT | NULL |
| `error_message` | TEXT | NULL |
| `trace_status` | TEXT | NOT NULL, CHECK IN (`disabled`,`submitted`,`confirmed`,`failed`) |
| `trace_id` | TEXT | NULL |
| `trace_url` | TEXT | NULL; enlace devuelto por LangSmith, si está disponible |
| `started_at` | TEXT | NOT NULL |
| `finished_at` | TEXT | NULL |

`INDEX(case_id, started_at)`.
`UNIQUE(question_message_id, attempt_no)` — cada intento queda identificado sin duplicar la
pregunta.
`CREATE UNIQUE INDEX ux_runs_one_active_per_case ON runs(case_id) WHERE status = 'running';` — la
base impone una sola ejecución activa por caso.

`trace_status`: `submitted` significa que el SDK no reportó error tras el envío síncrono y `flush`; `confirmed` solo se
asigna cuando `scripts/confirm_trace.py` verifica por API de lectura que la traza existe en
LangSmith. El código de la aplicación nunca escribe `confirmed`.

### 2.11 `run_steps`

| Campo | Tipo | Restricción |
|---|---|---|
| `id` | TEXT | PK |
| `run_id` | TEXT | NOT NULL, FK `runs(id)` ON DELETE CASCADE |
| `seq` | INTEGER | NOT NULL |
| `name` | TEXT | NOT NULL (`load_scope`, `retrieve`, `agent`, `tools`, `validate`, `repair`, `abstain`, `persist`) |
| `origin` | TEXT | NOT NULL, CHECK IN (`deterministic`,`model`) |
| `status` | TEXT | NOT NULL, CHECK IN (`ok`,`error`,`skipped`) |
| `duration_ms` | INTEGER | NULL |
| `detail_json` | TEXT | NULL |

`UNIQUE(run_id, seq)`.

### 2.12 `run_sources`

| Campo | Tipo | Restricción |
|---|---|---|
| `id` | TEXT | PK |
| `run_id` | TEXT | NOT NULL, FK `runs(id)` ON DELETE CASCADE |
| `chunk_id` | TEXT | NOT NULL, FK `document_chunks(id)` |
| `origin` | TEXT | NOT NULL, CHECK IN (`public_corpus`,`case_evidence`) |
| `rank` | INTEGER | NOT NULL |
| `score` | REAL | NOT NULL |
| `used_in_answer` | INTEGER | NOT NULL DEFAULT 0 |

`UNIQUE(run_id, chunk_id)`.

### 2.13 `run_tool_calls`

| Campo | Tipo | Restricción |
|---|---|---|
| `id` | TEXT | PK |
| `run_id` | TEXT | NOT NULL, FK `runs(id)` ON DELETE CASCADE |
| `seq` | INTEGER | NOT NULL |
| `tool_name` | TEXT | NOT NULL |
| `origin` | TEXT | NOT NULL, CHECK IN (`model_requested`,`deterministic`) |
| `arguments_json` | TEXT | NOT NULL |
| `result_summary_json` | TEXT | NULL |
| `status` | TEXT | NOT NULL, CHECK IN (`ok`,`invalid_arguments`,`error`) |
| `error_code` | TEXT | NULL |
| `duration_ms` | INTEGER | NULL |

`UNIQUE(run_id, seq)`.

### 2.14 `synthetic_datasets`

| Campo | Tipo | Restricción |
|---|---|---|
| `id` | TEXT | PK |
| `name` | TEXT | NOT NULL, UNIQUE |
| `version` | TEXT | NOT NULL |
| `seed` | INTEGER | NOT NULL |
| `checksum` | TEXT | NOT NULL, SHA-256 del archivo fuente |
| `applies_to_case_id` | TEXT | NULL, FK `cases(id)` |
| `description` | TEXT | NOT NULL |
| `created_at` | TEXT | NOT NULL |

### 2.15 `findings`

| Campo | Tipo | Restricción |
|---|---|---|
| `id` | TEXT | PK |
| `case_id` | TEXT | NOT NULL, FK `cases(id)` ON DELETE CASCADE |
| `asset_id` | TEXT | NOT NULL, FK `assets(id)` ON DELETE CASCADE |
| `dataset_id` | TEXT | NOT NULL, FK `synthetic_datasets(id)` |
| `title` | TEXT | NOT NULL |
| `severity_raw` | TEXT | NOT NULL (valor original de la fuente) |
| `severity_label` | TEXT | NOT NULL, CHECK IN (`Critical`,`High`,`Medium`,`Low`,`Info`) |
| `cvss_base` | REAL | NULL, CHECK entre 0 y 10 |
| `qid` | TEXT | NULL |
| `first_detected` | TEXT | NULL |
| `last_detected` | TEXT | NULL |
| `provenance` | TEXT | NOT NULL |
| `is_synthetic` | INTEGER | NOT NULL DEFAULT 1, CHECK IN (0,1) |
| `created_at` | TEXT | NOT NULL |

`INDEX(case_id, severity_label)`, `INDEX(case_id, asset_id)`, `INDEX(case_id, qid)`.

`severity_raw` y `severity_label` se conservan por separado: el valor original no se reescribe.

### 2.16 `finding_cves`

| Campo | Tipo | Restricción |
|---|---|---|
| `finding_id` | TEXT | NOT NULL, FK `findings(id)` ON DELETE CASCADE |
| `cve` | TEXT | NOT NULL |

`PRIMARY KEY(finding_id, cve)`, `INDEX(cve)`. Permite filtrar por CVE exacto sin interpretar
texto libre.

## 3. Estados

### Versión de documento

```text
pending ──> processing ──> available ──> superseded
                    │
                    ├──> no_usable_text ──(reintento)──> processing
                    └──> failed ──────────(reintento)──> processing
```

- `available` exige que todos sus fragmentos estén `indexed`.
- `superseded` se asigna a la versión anterior en la misma transacción que publica la nueva.
- Al arrancar, toda versión en `processing` pasa a `failed` con `error_code=interrupted`.

### Trabajo de ingesta

```text
queued ──> running ──> succeeded
                ├───> failed
                └───> interrupted ──(reintento)──> queued
```

### Ejecución

```text
running ──> succeeded | failed | timeout | interrupted
```

`outcome` solo se llena cuando la ejecución termina.

### Cita

```text
valid | rejected   (control automático)
unreviewed | supported | not_supported   (control humano, independiente)
```

## 4. Invariantes

1. **Alcance**: toda fila de negocio con `case_id` se consulta siempre a través de un
   `CaseScope`. Un repositorio no acepta un `case_id` suelto.
2. **Corpus separado**: `origin='public_corpus'` implica `case_id IS NULL`; `origin='case_evidence'`
   implica `case_id IS NOT NULL`. El corpus público no pertenece a ningún caso y se consulta desde
   la colección pública.
3. **Deduplicación**: dos versiones del mismo `scope_key` no comparten `sha256`.
4. **Consultable**: una versión es consultable solo si `status='available'` y es la
   `current_version_id` de su documento.
5. **Citable**: cualquier fragmento existente es citable, aunque su versión esté `superseded`. Si
   el fragmento o la versión desaparecen, la cita pasa a `unavailable` y se muestra el motivo.
6. **Sin borrado silencioso**: no hay borrado físico en este incremento. Invalidar es cambiar el
   estado y registrar el motivo.
7. **Conteos**: toda cifra de hallazgos se calcula con agregación sobre las mismas filas que se
   muestran, en la misma transacción.
8. **Evaluación**: ningún módulo de `src/` lee `data/eval/final/`.
9. **Fuente pública**: `documents.source_id` debe existir en `data/corpus/manifest.json`; se valida
   al arrancar y en pruebas.
10. **Alcance de mensajes y citas**: todo `message_id` y `citation_id` se resuelve dentro del
    `CaseScope`. Un identificador de otro caso produce `404`, igual que un documento o una
    ejecución ajenos.

## 5. Resolución de citas

```text
cita → chunk_id → document_chunks.version_id → document_versions.document_id
     → documents.origin → (case:<case_id> | public:<source_id>)
```

Reglas:

- La cita guarda `chunk_id` y `document_version_id`; no depende del documento «actual».
- Si la versión fue superada, la cita sigue resolviendo y la interfaz indica «versión superada».
- Si la cita textual no aparece literalmente en el fragmento (comparación normalizada), la cita se
  marca `rejected` y no se muestra.
- Si el fragmento no pertenece al caso autorizado ni al corpus público, la cita se rechaza y se
  registra como incidente de alcance.

## 6. Recuperación tras interrupción

1. Al arrancar: `runs.running → interrupted`, `ingestion_jobs.running → interrupted`,
   `document_versions.processing → failed(interrupted)`.
2. Un documento interrumpido nunca queda `available`.
3. Reintentar ingesta: si el texto extraído ya existe, se reutiliza; se rehacen fragmentos e
   índice con `upsert` por `(version_id, chunk_index)` y `chunk_id`.
4. Reconstruir índice de un caso: se recorren sus fragmentos `indexed`/`pending`, se recrea la
   colección si falta y se hace `upsert`. No se pierde ninguna cita.
5. Consistencia de memoria: al cargar un checkpoint se verifica que su `thread_id` coincida con la
   conversación; si falta o no coincide, se reconstruye desde `messages` y se registra el evento.

## 7. Nombres de colección (derivados, no persistidos)

```text
public__<modelo_slug>__<dim>
case__<case_id>__<modelo_slug>__<dim>
```

- `modelo_slug` normaliza el nombre del modelo de embeddings y se trunca para no exceder el límite
  de nombre de colección.
- El nombre se calcula en `retrieval/collections.py` a partir del alcance autorizado, el modelo y
  la dimensión. Nunca proviene de un argumento del modelo.
- Al arrancar se valida que el nombre cumpla el formato y la longitud admitidos por Chroma.
- El conteo de fragmentos se obtiene de `document_chunks`; no se persiste en un registro aparte.

## 8. Configuración persistida por ejecución

Cada `runs` guarda modelo, digest, contexto, temperatura, semilla, modelo de embeddings, dimensión
y versión del prompt. Sin esos campos no se puede reproducir ni comparar una respuesta.

## 9. Transacciones, concurrencia y reintentos

### Dos controles distintos

1. **Exclusión por caso** (persistida): una sola fila `runs` con `status='running'` por `case_id`,
   impuesta por el índice único parcial. La adquisición es atómica al insertar la ejecución.
2. **Límite global de generación** (en proceso): un semáforo de un permiso que envuelve la llamada
   al modelo. Se adquiere antes de crear la ejecución, con espera acotada
   (`SECGUARD_GENERATION_QUEUE_TIMEOUT_SECONDS`). Si no se adquiere, no se crea ejecución ni
   mensaje. Se libera en `finally`, después de persistir el resultado.

La aplicación corre en **un solo proceso y un worker**. El semáforo y la reconciliación de arranque
lo asumen.

### Límites transaccionales

- Cada escritura ocurre en una transacción corta y se confirma antes de la siguiente fase.
- **Ninguna transacción ni sesión de escritura permanece abierta durante la llamada al modelo.**
- Secuencia de un turno:
  1. Adquirir el semáforo global con espera acotada. Si falla, rechazar sin crear nada.
  2. `T1`: crear `runs` (`running`, `attempt_no`) y el mensaje de usuario. Commit. Si la exclusión
     por caso falla, liberar el semáforo y responder conflicto.
  3. Sin transacción abierta: recuperación y generación.
  4. `T2`: en **una sola transacción**, persistir el mensaje asistente, sus citas y controles, los
     pasos, las fuentes, las llamadas a herramientas y el **cierre de la ejecución** (`status`,
     `outcome`, `duration_ms`, `finished_at`, `answer_message_id`).
  5. Liberar el semáforo en `finally`.
- Si el proceso muere entre `T1` y `T2`, no existe mensaje asistente; la ejecución queda `running` y
  el arranque la marca `interrupted`.
- Si `T2` falla, no hay respuesta persistida. Se intenta cerrar la ejecución como `failed` en una
  transacción best-effort; si también falla, el arranque la marca `interrupted`.
- La desconexión del cliente no cancela el manejador síncrono ni libera los controles antes del
  cierre real.

### Memoria y checkpoints separados

El checkpointer de LangGraph vive en `storage/checkpoints.sqlite`, una base distinta. **No se
promete atomicidad entre bases.** Los mensajes de la base de aplicación son la fuente autoritativa:

- antes de cada turno se verifica que el `thread_id` coincida con la conversación;
- si el checkpoint quedó adelantado, se recorta desde los últimos mensajes persistidos;
- si falta o no coincide, se reconstruye desde `messages`;
- un fallo entre ambas bases no puede producir una respuesta visible sin cierre de ejecución,
  porque respuesta y cierre comparten la misma transacción.

### Reintentos

- Solo se reintenta una ejecución en estado `failed`, `timeout` o `interrupted` **y sin
  `answer_message_id`**.
- El reintento reutiliza el `question_message_id` original: no se inserta un mensaje de usuario
  nuevo.
- Se crea una fila nueva en `runs` con `attempt_no = max(attempt_no) + 1` y `retry_of_run_id`
  apuntando al intento anterior.
- Un intento exitoso no se reintenta.
- El mensaje asistente solo existe para el intento que terminó con respuesta.

### Tres solicitudes distintas

| Caso | Qué ocurre |
|---|---|
| Pregunta nueva tras un turno exitoso | Mensaje y ejecución nuevos, aunque el texto se repita |
| Reintento de una operación fallida | Misma pregunta, intento nuevo, sin respuesta previa |
| Envío duplicado con una ejecución activa | Rechazo, sin mensaje ni ejecución nuevos |

No hay idempotencia por clave de solicitud en este incremento.
