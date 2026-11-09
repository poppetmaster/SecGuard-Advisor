# Contrato evolucionado — `findings_query` con vulnerabilidades importadas

## Alcance

La herramienta se construye por turno con el `CaseScope` capturado en el servidor. El esquema no
incluye `case_id`, rutas, nombres de tabla ni SQL. El modelo puede elegir el origen, el snapshot y los
filtros; el servidor valida que el snapshot pertenezca al caso.

Se mantiene el nombre `findings_query` y la compatibilidad con hallazgos sintéticos. Los registros
importados no se convierten en documentos RAG ni en citas.

## Argumentos

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "origin": { "enum": ["all", "synthetic", "imported"], "default": "all" },
    "snapshot_id": { "type": "string", "maxLength": 32 },
    "asset": { "type": "string", "maxLength": 200 },
    "severity": { "enum": ["Critical", "High", "Medium", "Low", "Info"] },
    "severity_level": { "type": "integer", "minimum": 1, "maximum": 5 },
    "status_group": {
      "enum": ["pending_known", "fixed", "manual_review", "all"],
      "default": "pending_known"
    },
    "priority": { "type": "boolean" },
    "exploitability": {
      "enum": ["positive", "negative_no_info", "indeterminate"]
    },
    "malware": { "enum": ["positive", "negative_no_info", "indeterminate"] },
    "qid": { "type": "string", "pattern": "^[0-9]{1,10}$" },
    "cve": { "type": "string", "pattern": "^CVE-[0-9]{4}-[0-9]{4,7}$" },
    "group_by": {
      "enum": ["severity", "severity_level", "asset", "status", "priority", "origin"]
    },
    "detail": { "type": "boolean", "default": false },
    "limit": { "type": "integer", "minimum": 1, "maximum": 100, "default": 20 }
  }
}
```

Todos los filtros son opcionales. `limit` solo afecta al detalle; nunca a los conteos.

### Reglas de compatibilidad

- `origin` ausente equivale a `all`.
- `severity` conserva el enum sintético existente y solo es válido con `origin=synthetic` o
  `origin=all` cuando el caso no contiene importados.
- `severity_level` solo es válido con `origin=imported` o `origin=all` cuando el caso no contiene
  sintéticos.
- `status_group`, `snapshot_id`, `priority`, `exploitability` y `malware` solo aplican a
  `origin=imported`.
- Si `origin=all` y el caso contiene ambos orígenes, un filtro de severidad (`severity` o
  `severity_level`) sin origen produce `ambiguous_severity_filter`. No se convierte una escala en otra.
- `status_group` con `origin=all` en un caso mixto exige `origin=imported`; de lo contrario devuelve
  `origin_required_for_status_filter`.
- `snapshot_id` debe ser un snapshot confirmado del caso; si no, `snapshot_not_found`.
- `origin=imported` sin snapshots confirmados devuelve `snapshot: null`, `total: 0` y
  `empty_reason: "no_confirmed_import"`; no es una afirmación de ausencia de vulnerabilidades.
- El default `status_group=pending_known` solo se aplica a importados. Para sintéticos no cambia el
  comportamiento existente.

## Resultado con un solo origen

Si el caso solo tiene sintéticos, se conserva la forma existente y se añade procedencia:

```json
{
  "origin": "synthetic",
  "total": 4,
  "groups": [{ "key": "High", "count": 3 }],
  "dataset": { "name": "demo-findings", "version": "1", "checksum": "…", "is_synthetic": true },
  "severity_scale": "synthetic_labels",
  "items": [],
  "truncated": false
}
```

Si el caso solo tiene importados:

```json
{
  "origin": "imported",
  "snapshot": {
    "id": "imp_…",
    "sequence": 3,
    "confirmed_at": "2026-11-09T…",
    "csv_sha256": "…",
    "adapter_version": "qualys-csv-1"
  },
  "status_group": "pending_known",
  "total": 662,
  "groups": [{ "key": "4", "count": 162, "label": "Alta" }],
  "severity_scale": "project_1_5",
  "priority_counts": {
    "both_positive": 8,
    "exploitability_only": 121,
    "malware_only": 0,
    "neither_positive": 0,
    "indeterminate": 533
  },
  "items": [],
  "truncated": false
}
```

## Resultado con ambos orígenes

No se fusionan escalas ni filas en un `groups` sin etiqueta. El resultado incluye un bloque por
origen:

```json
{
  "origin": "all",
  "origins": [
    {
      "origin": "synthetic",
      "total": 4,
      "groups": [{ "key": "High", "count": 3 }],
      "severity_scale": "synthetic_labels",
      "dataset": { "name": "demo-findings", "version": "1", "is_synthetic": true }
    },
    {
      "origin": "imported",
      "snapshot": { "id": "imp_…", "sequence": 3 },
      "status_group": "pending_known",
      "total": 662,
      "groups": [{ "key": "4", "count": 162, "label": "Alta" }],
      "severity_scale": "project_1_5",
      "priority_counts": { "both_positive": 8, "exploitability_only": 121 }
    }
  ],
  "total": 666,
  "items": [],
  "truncated": false
}
```

`total` es la suma de los bloques, pero siempre está acompañado por `origins`. La respuesta del
agente debe mencionar el origen y el snapshot cuando corresponda.

## Detalle de un registro importado

```json
{
  "vulnerability_id": "…",
  "import_id": "imp_…",
  "row_number": 17,
  "asset": "activo-de-ejemplo",
  "title": "Título sintético de ejemplo",
  "qid": "900001",
  "status": "Active",
  "status_group": "pending_known",
  "severity_level": 4,
  "severity_label": "Alta",
  "severity_raw": "4",
  "priority": true,
  "priority_reason": "Explotabilidad positiva y malware positivo",
  "exploitability": "positive",
  "malware": "positive",
  "cves": ["CVE-2024-0001"],
  "first_detected": "01/10/2026 10:00:00",
  "last_detected": "02/01/2026 11:00:00",
  "provenance": "qualys:qualys-csv-1"
}
```

No se incluye `Results` completo, IP completa, rutas, `case_id` ni contenido de otros casos. La
etiqueta de activo es de presentación, no una identidad.

## Conteos

- `total` y `groups[].count` se calculan con `COUNT(*)` sobre la tabla de origen y exactamente los
  filtros aplicados.
- CVE se filtra con subconsulta `EXISTS`/`IN`; nunca se hace join que multiplique registros.
- Un registro con varios CVE cuenta una sola vez.
- `limit` solo limita `items`; `truncated` indica si hay más detalle que el límite.
- `priority_counts` se calcula por separado y no reemplaza la severidad.
- `Fixed` y `manual_review` no se suman a `pending_known`.

## Snapshot seleccionado

- Si `snapshot_id` no se envía, el servidor usa el último snapshot confirmado del caso por
  `confirmed_sequence`.
- La primera llamada de herramienta del turno fija `selected_import_id` en el estado del grafo; las
  siguientes llamadas del mismo turno lo reutilizan.
- Todas las respuestas incluyen el snapshot usado; si no hay snapshots, `snapshot: null`.
- Confirmar otro snapshot durante la respuesta no cambia el resultado ya fijado.
- El resumen histórico de `run_tool_calls` conserva el snapshot, filtros, totales, grupos, origen,
  prioridad e indicadores; no filas.

## Errores

| `status` | `error_code` | Cuándo | Efecto |
|---|---|---|---|
| `invalid_arguments` | `invalid_severity` | Etiqueta sintética inválida | Corregir |
| `invalid_arguments` | `invalid_severity_level` | Nivel fuera de 1–5 | Corregir |
| `invalid_arguments` | `invalid_status_group` | Grupo desconocido | Corregir |
| `invalid_arguments` | `invalid_priority` | Tipo incorrecto | Corregir |
| `invalid_arguments` | `invalid_exploitability` | Evaluación desconocida | Corregir |
| `invalid_arguments` | `invalid_malware` | Evaluación desconocida | Corregir |
| `invalid_arguments` | `invalid_qid` / `invalid_cve` / `limit_out_of_range` | Formato/límite | Corregir |
| `invalid_arguments` | `ambiguous_severity_filter` | Severidad sin origen en caso mixto | Pedir origen |
| `invalid_arguments` | `origin_required_for_status_filter` | Estado sin `origin=imported` | Pedir origen |
| `invalid_arguments` | `filter_not_applicable` | Filtro importado con origen sintético | Corregir |
| `invalid_arguments` | `snapshot_not_found` | Snapshot ajeno o no confirmado | Corregir |
| `error` | `tool_failed` | Fallo de base | Turno `failed` |
| `timeout` | `tool_timeout` | Excede el tiempo | Turno `timeout` |

Un error de argumentos no devuelve una lista vacía ni inventa un resultado.

## Invariantes

1. El alcance del caso nunca se toma del modelo.
2. No se acepta SQL, nombres de tabla, rutas ni ordenamientos arbitrarios.
3. Los conteos son recalculables y no se multiplican por CVE.
4. Los orígenes no se mezclan sin desglose.
5. Un snapshot no se suma con otro.
6. Un resultado vacío no afirma ausencia de vulnerabilidades.
7. No se envían filas, activos, resultados ni indicadores reales a trazas externas.
8. La compatibilidad sintética se conserva cuando el caso no tiene importados.
