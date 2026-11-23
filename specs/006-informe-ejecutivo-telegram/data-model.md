# Data Model — 006 Informe ejecutivo y notificaciones Telegram

**Fuente de verdad**: SQLite. **Artefactos**: `storage/reports/...`. **Migración**: aditiva, una
revisión por corte. El Corte A añade tablas nuevas y una extensión compatible de `runs` (005) para
la síntesis; no reescribe datos existentes ni cambia el significado de las filas de chat.

Convenciones: identificadores `String(32)` hexadecimales con `new_id()`; fechas ISO-8601 UTC en
`String(40)`; JSON canónico en `Text`; importes en `Numeric(18,9)`.

## 1. Informes

### `reports`

| Campo | Tipo | Regla |
|---|---|---|
| `id` | String(32) PK | `new_id()` |
| `case_id` | FK `cases.id` CASCADE | obligatorio |
| `created_by` | String(120) | identidad declarada |
| `created_at` | String(40) | UTC |

Índice: `(case_id, created_at)`.

### `report_versions`

La versión se crea en `generating`, se completa en `ready` y solo entonces se lista o publica. Una
versión `failed` se limpia y puede reutilizarse con la misma `generation_key`; nunca se sobrescribe
una versión `ready` anterior.

| Campo | Tipo | Regla |
|---|---|---|
| `id` | String(32) PK | |
| `report_id` | FK `reports.id` CASCADE | obligatorio |
| `case_id` | FK `cases.id` CASCADE | copia para aislamiento e índice |
| `version_number` | Integer | ≥1; único por `report_id` |
| `status` | String(20) | `generating`, `ready`, `failed`; solo `ready` se publica |
| `generation_key` | String(64) | nullable; único cuando no es nulo. Automático: `auto:<evaluation_id>`; manual: nulo |
| `snapshot_import_id` | FK `qualys_imports.id` RESTRICT | debe estar `confirmed` y del mismo caso |
| `snapshot_sequence` | Integer | copia de `confirmed_sequence` |
| `filters_json` | Text | filtros aplicados, canónicos |
| `dataset_json` | Text | dataset canónico (ver §2) |
| `dataset_sha256` | String(64) | SHA-256 del JSON canónico |
| `chart_specs_json` | Text | opciones ECharts canónicas |
| `synthesis_status` | String(20) | `not_requested`, `completed`, `unavailable`, `failed` |
| `ai_run_id` | FK `runs.id` SET NULL | solo si hubo síntesis |
| `summary_text` | Text | resumen factual o sintetizado |
| `focus_json` | Text | focos de atención |
| `recommendations_json` | Text | propuestas con `basis`, `claim_refs` y `evidence_refs`; ver `contracts/report-synthesis.md` |
| `limitations_json` | Text | límites, faltantes y cobertura |
| `author_declared` | String(120) | autor de la generación |
| `created_at` | String(40) | UTC |

Restricciones: `Unique(report_id, version_number)`, `Check(version_number >= 1)`,
`Check(synthesis_status IN (...))`, `Check(status IN ('generating','ready','failed'))` e índice único
parcial `(generation_key) WHERE generation_key IS NOT NULL`.
El Corte A no referencia tablas de C: `generation_key` es un texto opaco que el servicio recibe.

#### Creación o recuperación por `generation_key` (DEL-01)

1. La evaluación automática crea su `generation_key = "auto:" + evaluation.id` en la misma transacción
   de confirmación de importación.
2. El servicio de informes ejecuta un `INSERT ... ON CONFLICT(generation_key) DO NOTHING` y lee la
   fila resultante. Si ya existe, la reutiliza; si no, la crea una sola vez.
3. Después, en otra transacción corta, guarda `evaluation.report_version_id`. Si el proceso cae antes,
   el reintento usa la misma clave y recupera la versión existente.
4. Si cae después de guardar el vínculo, el reintento reutiliza versión y eventos.
5. Si cae después de crear eventos, la clave de idempotencia por versión/destinatario reutiliza esos
   eventos. Nunca se crea una versión nueva para eludir la idempotencia.

El manual puede usar `generation_key = NULL`; la unicidad de `(report_id, version_number)` sigue
protegiendo la regeneración manual.

### `report_artifacts`

| Campo | Tipo | Regla |
|---|---|---|
| `id` | String(32) PK | |
| `report_version_id` | FK CASCADE | obligatorio |
| `kind` | String(20) | `pdf`, `chart_svg` |
| `chart_key` | String(40) | `severity`, `assets`, `exploitability`, `malware`; `''` para PDF |
| `relative_path` | Text | relativo a `storage/reports/` |
| `sha256` | String(64) | |
| `bytes` | Integer | ≥0 |
| `created_at` | String(40) | |

`Unique(report_version_id, kind, chart_key)` con `chart_key` no nulo para evitar duplicados.

### Extensión de `runs` para la síntesis (Corte A)

La síntesis reutiliza `runs`, `ai_requests`, `provider_usage` y `provider_budget_ledger` en lugar de
crear una telemetría paralela. Cambios compatibles, en una reconstrucción controlada de SQLite:

| Cambio | Motivo |
|---|---|
| `conversation_id` pasa a nullable | La síntesis no pertenece a una conversación de chat |
| `kind` admite `report` además de `chat` | Distingue la ejecución de informe |
| `outcome` admite `report_ready` y `report_factual` | Evita reutilizar resultados de chat |
| Índice único de ejecución activa por caso se limita a `kind='chat'` | Permite una síntesis mientras hay un chat activo |
| `report_versions.ai_run_id` → `runs.id` | Enlaza la versión con su ejecución de síntesis |

Las filas existentes conservan `kind='chat'`, `conversation_id` no nulo y su índice. Las vistas de
chat y «Ver ejecución» filtran `kind='chat'`; el panel de uso incluye también `kind='report'` para
mostrar el costo real.

## 2. Dataset canónico (`report-dataset-v1`)

```json
{
  "schema_version": "report-dataset-v1",
  "case": {"id": "...", "title": "...", "scope": "...", "is_synthetic": true, "synthetic_notice": "..."},
  "snapshot": {"import_id": "...", "sequence": 3, "confirmed_at": "...", "csv_sha256": "...",
               "row_count": 100, "valid_rows": 100, "invalid_rows": 0, "warning_rows": 0,
               "manifest_status": "matched", "origin": "imported", "provenance": "private_qualys"},
  "filters": {"status_group": null, "severity_level": null, "asset": null, "qid": null,
              "cve": null, "exploitability": null, "malware": null, "priority": null},
  "base": {"total_rows": 100, "pending_known": 70, "fixed": 20, "manual_review": 10,
           "unknown_asset_rows": 2},
  "cards": {
    "pending": {"value": 70, "scope": "pending_known", "denominator": 100, "definition": "Active, New y Re-Opened"},
    "critical_pending": {"value": 12, "scope": "pending_known & severity_level=5", "denominator": 70},
    "high_pending": {"value": 21, "scope": "pending_known & severity_level=4", "denominator": 70},
    "distinct_assets_pending": {"value": 18, "scope": "pending_known", "denominator": 70,
                                "identifier": "FQDN > DNS > NetBIOS > IP", "unknown_asset_rows": 2},
    "exploitability_positive_pending": {"value": 30, "scope": "pending_known & exploitability_eval=positive", "denominator": 70},
    "malware_positive_pending": {"value": 8, "scope": "pending_known & malware_eval=positive", "denominator": 70},
    "both_positive_pending": {"value": 6, "scope": "pending_known & ambos positivos", "denominator": 70},
    "fixed": {"value": 20, "scope": "fixed", "denominator": 100},
    "manual_review": {"value": 10, "scope": "estado desconocido ∪ explotabilidad indeterminada ∪ malware indeterminado", "denominator": 100}
  },
  "severity": {"levels": [{"level": 1, "label": "Informativa", "pending": 0, "fixed": 0},
                          {"level": 2, "label": "Baja", "pending": 10, "fixed": 0},
                          {"level": 3, "label": "Media", "pending": 27, "fixed": 10},
                          {"level": 4, "label": "Alta", "pending": 21, "fixed": 8},
                          {"level": 5, "label": "Crítica", "pending": 12, "fixed": 2}],
               "denominator_pending": 70, "denominator_fixed": 20},
  "assets_top": {"top_n": 5, "total_assets": 20, "assets_with_critical_or_high": 9,
                 "records_critical_or_high": 33, "recorted": true,
                 "items": [{"alias": "Activo 01", "internal_label": "host-01.corp.local",
                            "critical": 5, "high": 3, "total": 8}],
                 "tie_break": "critical desc, high desc, total desc, label asc",
                 "others": {"alias": "Otros", "assets": 4, "records": 7}},
  "exploitability": {"positive": 30, "negative_no_info": 30, "indeterminate": 10, "denominator": 70},
  "malware": {"positive": 8, "negative_no_info": 52, "indeterminate": 10, "denominator": 70},
  "coverage": {"exploitability_known_ratio": 0.86, "malware_known_ratio": 0.86,
               "severity_known_ratio": 1.0, "missing_fields": ["FQDN en 2 registros"]},
  "limitations": ["Los indicadores vacíos se muestran como no informados; no son negativos.",
                  "Un total 0 no demuestra ausencia de vulnerabilidades."],
  "metric_versions": {"severity_scale": "1-5", "status_policy_version": "...", "adapter_version": "..."}
}
```

Reglas del dataset:

- Todos los agregados usan filas de `qualys_vulnerabilities` del snapshot; ningún `JOIN` a CVEs en
  conteos.
- `manual_review` es una unión contada una vez; no se suma con las distribuciones.
- `exploitability` y `malware` son independientes y comparten denominador `pending_known`; no se
  suman entre sí.
- `assets_top` declara `total_assets`, `assets_with_critical_or_high`, `recorted` y el grupo «Otros».
- `internal_label` solo se usa en la vista local; el contenido saliente usa `alias`.
- El hash se calcula sobre el JSON con `sort_keys=True`, separadores `(",", ":")`, UTF-8 y sin
  espacios.

## 3. `chart-specs-v1`

```json
{
  "schema_version": "report-charts-v1",
  "severity": {"title": "...", "conclusion": "...", "denominator_label": "...", "option": {}},
  "assets": {"title": "...", "conclusion": "...", "denominator_label": "...", "option": {}},
  "exploitability": {"title": "...", "conclusion": "...", "denominator_label": "...", "option": {}},
  "malware": {"title": "...", "conclusion": "...", "denominator_label": "...", "option": {}}
}
```

`option` es un objeto ECharts serializable, sin funciones. La web lo pasa a `echarts.init`; el script
Node lo renderiza a SVG. Títulos y conclusiones se calculan en `metrics.py`.

## 4. Confirmación y contenido aprobado (Corte B)

### `report_confirmations`

| Campo | Tipo | Regla |
|---|---|---|
| `id` | String(32) PK | |
| `case_id` | FK CASCADE | |
| `report_version_id` | FK CASCADE | |
| `manifest_json` | Text | manifiesto canónico `report-manifest-v1` |
| `manifest_sha256` | String(64) | SHA-256 del manifiesto canónico |
| `contacts_json` | Text | ids + alias + fingerprint de cada destinatario |
| `created_by` | String(120) | identidad declarada |
| `created_at` | String(40) | |
| `invalidated_at` | String(40) | nulo mientras sea válida |

Una confirmación solo es válida si `invalidated_at IS NULL`, no existe una versión posterior del
informe y `manifest_sha256` coincide con el manifiesto recalculado de la versión y los destinatarios
actuales.

### Manifiesto canónico `report-manifest-v1`

```json
{
  "schema_version": "report-manifest-v1",
  "case_id": "...",
  "report_id": "...",
  "report_version_id": "...",
  "report_version_number": 3,
  "dataset_sha256": "...",
  "outbound_text": "...",
  "outbound_text_sha256": "...",
  "pdf_sha256": "...",
  "content_policy": {"include_aliases": true, "allow_ip": false,
                     "allow_internal_names": false, "include_results": false,
                     "include_case_title": false, "detail_level": "executive"},
  "recipients": [{"contact_id": "...", "alias": "...", "chat_fingerprint": "..."}],
  "recipients_sha256": "..."
}
```

La procedencia `private_qualys` impide enviar agregados a un proveedor externo; solo
`synthetic_public` con autorización `fictional_case` puede habilitar la síntesis externa. El mismo
manifiesto se usa para la confirmación manual, la activación/evaluación de una regla y la ejecución. Antes de llamar a Telegram, el ejecutor recalcula y compara `manifest_sha256`; una
discrepancia bloquea el envío. El manifiesto no contiene token, `chat_id` completo ni contenido
privado adicional.


## 5. Contactos y canales

### `contact_channels`

| Campo | Tipo | Regla |
|---|---|---|
| `id` | String(32) PK | |
| `alias` | String(80) | obligatorio, no vacío |
| `channel` | String(20) | solo `telegram` |
| `chat_id` | String(64) | obligatorio; no se registra en logs |
| `chat_type` | String(20) | `private`, `group`, `supergroup`, `channel` |
| `display_name` | String(200) | opcional |
| `status` | String(20) | `unverified`, `verified`, `revoked`, `disabled` |
| `verification_method` | String(40) | `getchat_code_v1` |
| `verified_at` | String(40) | obligatorio si `verified` |
| `verified_by` | String(120) | identidad declarada |
| `verification_evidence` | Text | método, resultado de `getChat`, hash del código; sin token |
| `chat_fingerprint` | String(64) | SHA-256(bot_id + chat_id) |
| `consent_status` | String(20) | `pending`, `granted`, `revoked` |
| `consent_at` | String(40) | obligatorio si `granted` |
| `active` | Boolean | por defecto `false` |
| `created_at`, `updated_at` | String(40) | |

`Unique(channel, chat_id)`. `Check(status IN (...))`, `Check(verified_at IS NOT NULL OR status != 'verified')`.

### `contact_case_links`

| Campo | Tipo | Regla |
|---|---|---|
| `contact_id` | FK CASCADE | PK compuesta |
| `case_id` | FK CASCADE | PK compuesta |
| `authorized` | Boolean | por defecto `false` |
| `created_at` | String(40) | |

Solo un vínculo `authorized = true` habilita el destinatario para ese caso.

### `contact_verification_challenges`

**Corte B.** Persiste el desafío del código de verificación; es independiente del envío de informes.

| Campo | Tipo | Regla |
|---|---|---|
| `id` | String(32) PK | |
| `contact_id` | FK `contact_channels.id` CASCADE | obligatorio |
| `bot_fingerprint` | String(64) | SHA-256 del bot que emite el código |
| `code_sha256` | String(64) | SHA-256 del código; nunca el código en claro |
| `purpose` | String(20) | solo `contact_verification` |
| `status` | String(20) | `pending`, `consumed`, `expired`, `locked` |
| `created_at` | String(40) | |
| `expires_at` | String(40) | creación + 10 minutos |
| `attempts` | Integer | ≥0; máximo 3 |
| `max_attempts` | Integer | 3 |
| `consumed_at` | String(40) | obligatorio si `consumed` |
| `last_sent_at` | String(40) | límite de reenvíos |
| `request_count` | Integer | ≥1; máximo 3 por ventana |
| `window_started_at` | String(40) | ventana de límite de solicitudes |

Índice `(contact_id, status)`. `Check(status IN ('pending','consumed','expired','locked'))` y
`Check(status != 'consumed' OR consumed_at IS NOT NULL)`. Un desafío `consumed`, `expired` o `locked`
no valida ningún código. El token del bot no se persiste; el vínculo con el bot se guarda como
`bot_fingerprint`.

## 6. Reglas (Corte C)

### `notification_rules`

| Campo | Tipo | Regla |
|---|---|---|
| `id` | String(32) PK | |
| `case_id` | FK CASCADE | |
| `version` | Integer | ≥1; único por caso |
| `status` | String(20) | `draft`, `active`, `disabled`, `superseded` |
| `trigger_type` | String(30) | solo `qualys_import_confirmed` |
| `conditions_json` | Text | filtros y condiciones exactas |
| `content_policy_json` | Text | contenido y detalle permitido |
| `synthesis_policy` | String(20) | `factual_only` (defecto) o `ai_if_budget` |
| `author_declared` | String(120) | obligatorio para activar |
| `content_sha256` | String(64) | hash de condiciones + política + destinatarios |
| `created_at`, `activated_at`, `deactivated_at` | String(40) | |
| `supersedes_rule_id` | FK self SET NULL | versión anterior |

`Unique(case_id, version)`. Solo `active` puede disparar envíos. Cambiar condiciones, destinatarios o
política exige una versión nueva y `content_sha256` distinto.

### `notification_rule_contacts`

`rule_id` + `contact_id` (PK compuesta). Solo contactos verificados, con consentimiento `granted`,
activos y vinculados al caso.

### `notification_rule_evaluations` (outbox de evaluación, Corte C)

| Campo | Tipo | Regla |
|---|---|---|
| `id` | String(32) PK | |
| `case_id` | FK CASCADE | |
| `import_id` | FK `qualys_imports.id` | confirmado |
| `rule_id` | FK CASCADE | |
| `generation_key` | String(64) | **UNIQUE**, no nulo; `auto:<evaluation.id>` |
| `report_version_id` | FK `report_versions.id` SET NULL | versión generada; se conserva para reintentos |
| `status` | String(20) | `pending`, `claimed`, `done`, `skipped`, `failed` |
| `reason_code` | String(60) | motivo de omisión |
| `error_code` | String(60) | error acotado |
| `created_at`, `claimed_at`, `finished_at` | String(40) | |

`Unique(rule_id, import_id)` impide reevaluar la misma regla para la misma importación confirmada.
`generation_key` es único y estable; una vez creada la versión, `report_version_id` no se borra ni se
sustituye por una versión nueva en reintentos o reinicios. La recuperación usa la misma clave para
adoptar una versión huérfana.

## 7. Eventos y entrega (Corte B)

### `notification_events`

| Campo | Tipo | Regla |
|---|---|---|
| `id` | String(32) PK | |
| `case_id` | FK CASCADE | |
| `report_version_id` | FK CASCADE | |
| `contact_id` | FK CASCADE | |
| `mode` | String(20) | `manual`, `automatic` (metadato) |
| `rule_id` | FK SET NULL | nulo en manual |
| `rule_version` | Integer | copia |
| `idempotency_key` | String(64) | **UNIQUE**; SHA-256(case/version/contact) |
| `manifest_json` | Text | manifiesto aprobado `report-manifest-v1` |
| `manifest_sha256` | String(64) | hash del manifiesto ejecutado |
| `content_policy_json` | Text | política aplicada (copia del manifiesto) |
| `content_sha256` | String(64) | texto saliente + PDF (copia del manifiesto) |
| `confirmed_by` | String(120) | obligatorio en manual |
| `confirmed_at` | String(40) | obligatorio en manual |
| `status` | String(20) | ver §8 |
| `created_at`, `updated_at` | String(40) | |

Índice `(case_id, status)`, `(report_version_id)`.

### `notification_components`

| Campo | Tipo | Regla |
|---|---|---|
| `id` | String(32) PK | |
| `event_id` | FK CASCADE | |
| `kind` | String(20) | `summary`, `document` |
| `status` | String(20) | `prepared`, `requested`, `accepted`, `failed`, `uncertain`, `skipped` |
| `attempt_count` | Integer | ≥0 |
| `provider_message_id` | String(128) | si existe |
| `error_code` | String(60) | código seguro |
| `updated_at` | String(40) | |

`Unique(event_id, kind)`.

### `notification_attempts`

| Campo | Tipo | Regla |
|---|---|---|
| `id` | String(32) PK | |
| `event_id` | FK CASCADE | |
| `component_kind` | String(20) | `summary`, `document` |
| `attempt_no` | Integer | ≥1 |
| `status` | String(20) | `requested`, `accepted`, `failed`, `uncertain` |
| `requested_at`, `finished_at` | String(40) | |
| `http_status` | Integer | opcional |
| `error_code` | String(60) | opcional |
| `provider_message_id` | String(128) | opcional |
| `duration_ms` | Integer | opcional |
| `evidence_note` | Text | acotado; sin secretos ni contenido |

`Unique(event_id, component_kind, attempt_no)`.

## 8. Máquina de estados

### Desafío de verificación (Corte B)

```text
pending ──código correcto──▶ consumed
pending ──expira──▶ expired
pending ──3 intentos fallidos──▶ locked
```

Un desafío `consumed`, `expired` o `locked` no se reutiliza. Un nuevo envío de código crea otro
desafío; el anterior queda invalidado por estado.

### Evento

```text
prepared ──encolar──▶ queued ──reclamo──▶ sending
sending ──todos aceptados──▶ accepted
sending ──alguno aceptado y otro falla/pendiente──▶ partial
sending ──todos fallan definitivamente──▶ failed
sending ──algún timeout/sin respuesta──▶ uncertain
prepared/queued ──bloqueo previo──▶ skipped
```

Reglas:

- `accepted` es terminal para el evento; no se reenvía.
- `partial` permite reintentar solo componentes no aceptados.
- `uncertain` no se reintenta solo; requiere decisión humana.
- Un fallo de envío nunca revierte la importación confirmada.

### Componente

```text
prepared ─▶ requested ─▶ accepted | failed | uncertain
```

- `accepted` no vuelve a `requested`.
- Un reintento crea un nuevo `notification_attempt`, no un nuevo evento.
- `skipped` solo antes de la primera solicitud (destinatario inválido, política, límite).

## 9. Invariantes

1. Todo registro de informe, evento, regla y contacto se filtra por `case_id` antes de consultar.
2. `report_versions` y sus artefactos no se actualizan después de crearse.
3. `notification_events.idempotency_key` es única; el modo no participa.
4. Un componente `accepted` no se reenvía.
5. Ninguna transacción permanece abierta durante una llamada a Telegram.
6. `notification_rule_evaluations` es única por regla + importación confirmada.
7. El token nunca se persiste en SQLite ni se muestra; el `chat_id` no aparece en logs.
8. `manual_review` no se suma con indicadores; `exploitability` y `malware` no se suman entre sí.
9. Los conteos no se multiplican por CVE.
10. Una versión histórica no cambia al importar otro CSV.
11. El envío del código de verificación no exige verificación, consentimiento ni vínculo al caso; el
    envío de un informe sí exige los tres.
12. Un desafío de verificación nunca persiste el código en claro ni el token.
13. La ejecución de un informe compara `manifest_sha256` con el manifiesto aprobado; una discrepancia
    bloquea el envío.
14. Una evaluación automática conserva `report_version_id` y reutiliza los eventos existentes en
    reintentos o reinicios; no crea una versión nueva para eludir la idempotencia.
15. `report_versions.generation_key` es único cuando no es nulo; la creación o recuperación usa
    `INSERT ... ON CONFLICT DO NOTHING` y una lectura posterior.
16. Antes de cada componente (resumen y PDF), el ejecutor revalida destinatario, consentimiento,
    vínculo, manifiesto y regla si aplica. Un componente aceptado se conserva; los restantes quedan
    `skipped` con motivo.
