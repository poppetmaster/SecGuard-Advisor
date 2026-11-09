# Data Model — Vulnerabilidades Qualys

**Feature**: `002-qualys-findings-import`
**Estado**: diseño; no se han creado tablas ni migraciones.

## Principios

- Cada importación confirmada es una **instantánea inmutable** del caso.
- No existe una identidad estable de vulnerabilidad entre reportes.
- Las filas se identifican por `(import_id, row_number)`, no por una clave de vulnerabilidad.
- Los registros Qualys son datos estructurados; no son fragmentos, documentos ni entradas de Chroma.
- Las tablas sintéticas existentes (`synthetic_datasets`, `assets`, `findings`, `finding_cves`) no se
  modifican.
- La migración es aditiva y reversible.

## 1. `qualys_imports`

Representa una carga/validación y, si se confirma, una instantánea histórica.

| Campo | Tipo | Restricción |
|---|---|---|
| `id` | TEXT(32) | PK, `new_id()` |
| `case_id` | TEXT(32) | FK `cases.id` `ON DELETE CASCADE`, NOT NULL |
| `status` | TEXT(20) | NOT NULL, `CHECK IN ('validating','staged','rejected','confirmed','cancelled','expired','failed')` |
| `original_filename` | TEXT | NOT NULL; solo metadato local |
| `csv_sha256` | TEXT(64) | NOT NULL |
| `csv_bytes` | INTEGER | NOT NULL, `>= 0` |
| `manifest_sha256` | TEXT(64) | NULL; solo si se aporta el manifiesto de referencia |
| `manifest_status` | TEXT(20) | NOT NULL, `CHECK IN ('absent','matched','mismatch','invalid')`; default `absent` |
| `row_count` | INTEGER | NOT NULL, `>= 0` |
| `valid_rows` | INTEGER | NOT NULL, `>= 0` |
| `invalid_rows` | INTEGER | NOT NULL, `>= 0` |
| `warning_rows` | INTEGER | NOT NULL, `>= 0` |
| `manual_review_rows` | INTEGER | NOT NULL, `>= 0` |
| `possible_repeat_groups` | INTEGER | NOT NULL, `>= 0` |
| `possible_repeat_rows` | INTEGER | NOT NULL, `>= 0` |
| `status_counts_json` | TEXT | NOT NULL; conteos por estado original |
| `severity_counts_json` | TEXT | NOT NULL; conteos por nivel 1–5 |
| `exploitability_counts_json` | TEXT | NOT NULL; `positive`, `negative_no_info`, `indeterminate` |
| `malware_counts_json` | TEXT | NOT NULL; `positive`, `negative_no_info`, `indeterminate` |
| `priority_counts_json` | TEXT | NOT NULL; solo `both_positive`; no mezcla las distribuciones de indicadores |
| `summary_json` | TEXT | NOT NULL; resumen agregado de preview, sin filas |
| `adapter_version` | TEXT(60) | NOT NULL |
| `severity_policy_version` | TEXT(60) | NOT NULL |
| `status_policy_version` | TEXT(60) | NOT NULL |
| `priority_rule_version` | TEXT(60) | NOT NULL |
| `created_at` | TEXT(40) | NOT NULL |
| `validated_at` | TEXT(40) | NULL |
| `confirmed_at` | TEXT(40) | NULL |
| `cancelled_at` | TEXT(40) | NULL |
| `expires_at` | TEXT(40) | NULL; para `staged`/`rejected` |
| `confirmed_sequence` | INTEGER | NULL; `>= 1`; asignado al confirmar |
| `error_code` | TEXT(60) | NULL |
| `error_message` | TEXT | NULL; mensaje comprensible, sin filas |

### Restricciones e índices

- `INDEX ix_qualys_imports_case_status (case_id, status)`.
- `INDEX ix_qualys_imports_case_sequence (case_id, confirmed_sequence)`.
- `UNIQUE INDEX ux_qualys_imports_confirmed_hash (case_id, csv_sha256) WHERE status = 'confirmed'`.
  Evita confirmar dos veces el mismo contenido en el mismo caso.
- `UNIQUE INDEX ux_qualys_imports_confirmed_sequence (case_id, confirmed_sequence)
  WHERE confirmed_sequence IS NOT NULL`. Garantiza la secuencia local.
- `CHECK confirmed_sequence IS NULL OR confirmed_sequence >= 1`.
- `CHECK status != 'staged' OR invalid_rows = 0`.
- `CHECK status != 'confirmed' OR invalid_rows = 0`.
- `CHECK status NOT IN ('staged','confirmed') OR row_count >= 1`.
- `CHECK manifest_status != 'matched' OR manifest_sha256 IS NOT NULL`.
- `CHECK status != 'confirmed' OR confirmed_sequence IS NOT NULL`.

- `CHECK confirmed_at IS NULL OR status = 'confirmed'` (la transición se valida en servicio además
  del check).
- `CHECK status != 'confirmed' OR confirmed_at IS NOT NULL`.

### Estados y transiciones

```text
validating ──todo válido──> staged ──confirmar──> confirmed
     │                        │
     ├──error bloqueante──> rejected ──cancelar/expirar──> cancelled/expired
     ├──error interno─────> failed
     └──cancelar──────────> cancelled
```

- `validating`: mientras se lee/valida; no visible como snapshot.
- `staged`: validación preparada, todas las filas válidas, sin errores bloqueantes; visible en
  preview y confirmable; no consultable por `findings_query` hasta confirmar.
- `confirmed`: instantánea histórica consultable; inmutable.
- `cancelled`: descartada por la persona; sus filas/issues se eliminan en la limpieza.
- `expired`: staging/rechazo abandonado; se limpia; la persona debe volver a cargar.
- `rejected`: archivo con error estructural, de encabezado, contenido obligatorio, hash, cantidad,
  límite, archivo vacío o manifiesto inválido/discrepante; no confirmable y sin filas en
  `qualys_vulnerabilities`. La preview muestra cantidades y
  motivos; la persona cancela o carga un archivo corregido.
- `failed`: error interno/transacción; no hay snapshot consultable.

## 2. `qualys_vulnerabilities`

Una fila lógica de una instantánea. No representa una vulnerabilidad única entre reportes.

| Campo | Tipo | Restricción |
|---|---|---|
| `id` | TEXT(32) | PK |
| `import_id` | TEXT(32) | FK `qualys_imports.id` `ON DELETE CASCADE`, NOT NULL |
| `case_id` | TEXT(32) | FK `cases.id` `ON DELETE CASCADE`, NOT NULL (desnormalizado para alcance) |
| `row_number` | INTEGER | NOT NULL, `>= 1`; posición lógica, sin contar encabezado |
| `raw_json` | TEXT | NOT NULL; las 41 columnas originales, valores tal como llegaron |
| `asset_label` | TEXT(200) | NOT NULL; etiqueta de presentación derivada, no identidad |
| `ip` | TEXT(64) | NULL |
| `dns` | TEXT(200) | NULL |
| `netbios` | TEXT(200) | NULL |
| `fqdn` | TEXT(200) | NULL |
| `qid` | TEXT(20) | NOT NULL; dígitos |
| `title` | TEXT | NOT NULL |
| `vuln_type` | TEXT(20) | NULL; `Type` original normalizado |
| `status_raw` | TEXT(40) | NOT NULL; valor original |
| `status_normalized` | TEXT(20) | NOT NULL, `active/new/reopened/fixed/manual_review` |
| `status_group` | TEXT(20) | NOT NULL, `pending_known/fixed/manual_review` |
| `severity_raw` | TEXT(20) | NOT NULL; `Severity` original |
| `severity_level` | INTEGER | NOT NULL, `1..5` |
| `severity_label` | TEXT(20) | NOT NULL; Informativa/Baja/Media/Alta/Crítica |
| `severity_policy_version` | TEXT(60) | NOT NULL |
| `port` | INTEGER | NULL; vacío se conserva como NULL |
| `protocol` | TEXT(20) | NULL |
| `first_detected` | TEXT(40) | NULL; valor original |
| `last_detected` | TEXT(40) | NULL |
| `first_detected_normalized` | TEXT(40) | NULL; `MM/DD/YYYY HH:MM:SS`, sin zona horaria |
| `last_detected_normalized` | TEXT(40) | NULL |
| `date_last_fixed` | TEXT(40) | NULL |
| `first_reopened` | TEXT(40) | NULL |
| `last_reopened` | TEXT(40) | NULL |
| `times_detected` | INTEGER | NULL, `>= 0` |
| `times_reopened` | INTEGER | NULL, `>= 0` |
| `exploitability_raw` | TEXT | NULL; valor original completo |
| `exploitability_eval` | TEXT(20) | NOT NULL, `positive/negative_no_info/indeterminate` |
| `exploitability_reason` | TEXT(200) | NULL; motivo acotado, sin contenido real |
| `malware_raw` | TEXT | NULL; valor original completo |
| `malware_eval` | TEXT(20) | NOT NULL, `positive/negative_no_info/indeterminate` |
| `malware_reason` | TEXT(200) | NULL |
| `priority_flag` | BOOLEAN | NOT NULL, default false |
| `priority_reason` | TEXT(300) | NULL; motivo de la conjunción |
| `priority_rule_version` | TEXT(60) | NOT NULL |
| `vendor_metrics_json` | TEXT | NULL; QDS/ARS/ACS/TruRisk originales, sin equivalencias |
| `created_at` | TEXT(40) | NOT NULL |

### Restricciones e índices

- `UNIQUE (import_id, row_number)`.
- `INDEX ix_qualys_vulns_case_import (case_id, import_id)`.
- `INDEX ix_qualys_vulns_case_status (case_id, status_group)`.
- `INDEX ix_qualys_vulns_case_severity (case_id, severity_level)`.
- `INDEX ix_qualys_vulns_case_qid (case_id, qid)`.
- `INDEX ix_qualys_vulns_case_asset (case_id, asset_label)`.
- `INDEX ix_qualys_vulns_case_priority (case_id, priority_flag)`.
- `INDEX ix_qualys_vulns_case_indicators (case_id, exploitability_eval, malware_eval)`.
- `CHECK row_number >= 1`.
- `CHECK severity_level BETWEEN 1 AND 5`.
- `CHECK status_normalized IN ('active','new','reopened','fixed','manual_review')`.
- `CHECK status_group IN ('pending_known','fixed','manual_review')`.
- `CHECK exploitability_eval IN ('positive','negative_no_info','indeterminate')`.
- `CHECK malware_eval IN ('positive','negative_no_info','indeterminate')`.
- `CHECK (priority_flag = 0) OR (exploitability_eval = 'positive' AND malware_eval = 'positive')`.

### Derivaciones

- `asset_label`: `FQDN` → `DNS` → `NetBIOS` → `IP`, normalizado y acotado. Es una etiqueta de
  presentación; no se usa para afirmar que dos filas son la misma vulnerabilidad.
- `status_normalized`: `Active`→`active`, `New`→`new`, `Re-Opened`→`reopened`, `Fixed`→`fixed`;
  cualquier otro valor→`manual_review`.
- `status_group`: `active/new/reopened`→`pending_known`, `fixed`→`fixed`, `manual_review`→
  `manual_review`.
- `severity_label`: política `project-severity-1-5-v1`.
- `priority_flag`: solo si `exploitability_eval = positive` y `malware_eval = positive`.
- `vendor_metrics_json`: conserva QDS/ARS/ACS/TruRisk y sus nombres, sin mapearlos a CVSS.

### Filas inválidas, staging y confirmación

`qualys_vulnerabilities` contiene solo filas de un archivo `staged` o `confirmed`; un archivo
`rejected` no inserta filas en esa tabla. Las filas inválidas se representan en
`qualys_import_issues` con `row_number`, `code`, `field` y un mensaje sin valores reales. La vista
previa de un archivo rechazado muestra cantidades y motivos, no una vista de filas válidas.

No existe aceptación parcial ni control para «aceptar solo filas válidas». Una fila inválida bloquea
la confirmación del archivo completo. Un archivo vacío o sin filas se registra como `rejected` con
`csv_bytes=0`, `row_count=0`, `valid_rows=0`, `invalid_rows=0` y `error_code='empty_file'`; no se
permite `staged` ni `confirmed` con 0 filas.

El manifiesto no es un archivo del formulario. El servicio de validación/aceptación recibe una ruta
opcional y registra `manifest_status`: `absent`, `matched`, `mismatch` o `invalid`. `mismatch` e
`invalid` dejan la importación en `rejected`; `absent` no impide validar el CSV. La vista previa web
normal no recibe manifiesto y no promete comparación.

Las filas de `staged` son datos temporales de validación; solo al pasar a `confirmed` se convierten
en instantánea consultable. `findings_query` y la tabla de «Vulnerabilidades» filtran siempre por
`status='confirmed'`.

## 3. `qualys_vulnerability_cves`

| Campo | Tipo | Restricción |
|---|---|---|
| `vulnerability_id` | TEXT(32) | FK `qualys_vulnerabilities.id` `ON DELETE CASCADE`, PK |
| `cve` | TEXT(20) | PK; formato `CVE-AAAA-NNNN` |

- `INDEX ix_qualys_vuln_cves_cve (cve)`.
- `cve` usa `CVE-AAAA-NNNN` con 4–7 dígitos en la secuencia final; se valida en aplicación.
- La PK compuesta evita duplicar el mismo CVE en una fila.
- Los conteos usan `EXISTS`/`IN` sobre esta tabla; no se hace join que multiplique filas.

## 4. `qualys_import_issues`

| Campo | Tipo | Restricción |
|---|---|---|
| `id` | TEXT(32) | PK |
| `import_id` | TEXT(32) | FK `qualys_imports.id` `ON DELETE CASCADE`, NOT NULL |
| `row_number` | INTEGER | NULL; NULL para issues de archivo/encabezado |
| `severity` | TEXT(20) | `CHECK IN ('error','warning','manual_review')` |
| `code` | TEXT(60) | NOT NULL; código estable |
| `field` | TEXT(60) | NULL; columna afectada |
| `message` | TEXT | NOT NULL; mensaje comprensible, sin valores reales |
| `created_at` | TEXT(40) | NOT NULL |

- `error` es bloqueante: si existe al menos uno, la importación queda `rejected` y no se confirma.
- `warning` y `manual_review` no bloquean por sí solos: estado desconocido, indicador indeterminado,
  posible repetición o celda opcional vacía.
- `INDEX ix_qualys_import_issues_import (import_id, severity)`.
- `INDEX ix_qualys_import_issues_row (import_id, row_number)`.
- Un issue no incluye la fila completa ni el valor original; el `raw_json` ya está en la fila.

## 5. Relaciones

```text
cases 1──N qualys_imports 1──N qualys_vulnerabilities 1──N qualys_vulnerability_cves
                     │
                     └──N qualys_import_issues

cases 1──N findings (sintéticos, sin cambios)
runs 1──N run_tool_calls (resumen guarda snapshot_id y filtros)
```

`run_tool_calls.result_summary_json` no tiene FK a `qualys_imports` para no acoplar la evidencia
histórica a una fila que podría eliminarse en staging. El resumen guarda el `import_id` de una
instantánea confirmada, que nunca se borra.

## 6. Consulta y snapshot seleccionado

- `findings_query` resuelve el snapshot por defecto como:
  `SELECT id FROM qualys_imports WHERE case_id = :case_id AND status = 'confirmed'
   ORDER BY confirmed_sequence DESC LIMIT 1`.
- La primera llamada de herramienta del turno guarda `selected_import_id` en el estado del grafo.
  Todas las llamadas posteriores del mismo turno lo reutilizan.
- `snapshot_id` explícito solo se acepta si pertenece al caso y está `confirmed`. Un `snapshot_id`
  distinto tras la fijación devuelve `snapshot_locked`; un turno nuevo puede seleccionar otra
  importación.
- El resumen histórico de la herramienta conserva: `snapshot_id`, `confirmed_sequence`,
  `status_group`, `origin`, filtros, totales, grupos, prioridad e indicadores. No conserva filas.
- La página de ejecución lee el resumen; si recalcula detalle, lo etiqueta como consulta actual.

## 7. Migración

- Nueva revisión Alembic después de `9c3e4f5a6b7d` (`add_qualys_vulnerability_snapshots`).
- Crea las cuatro tablas, checks e índices; no altera tablas existentes.
- `downgrade` elimina las tablas nuevas en orden de dependencias.
- No se ejecuta en este comando; la implementación la creará y probará.

## 8. Limpieza y retención

- `staged`, `rejected`, `cancelled`, `expired` y `failed` pueden limpiarse; `confirmed` nunca.
- Al iniciar o antes de una nueva validación, expirar `staged` con `expires_at < now` y borrar sus
  filas/issues en una transacción corta.
- Cancelar solo afecta a un `staged` o `rejected`; si ya está `confirmed`, responde conflicto y no borra.
- La base y los archivos locales se mantienen fuera de Git; no se copian a fixtures.

## 9. Compatibilidad con el primer incremento

- `findings`, `finding_cves`, `synthetic_datasets` y `assets` no cambian.
- `run_tool_calls` no cambia de esquema; su JSON se extiende.
- `runs`, citas, revisión humana, memoria y presupuesto no cambian.
- Las consultas sintéticas conservan sus etiquetas y resultados cuando el caso no tiene imports.
- Las consultas mixtas no convierten escalas ni suman orígenes sin desglose.
