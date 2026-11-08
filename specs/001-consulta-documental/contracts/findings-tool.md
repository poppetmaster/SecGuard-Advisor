# Contrato de la herramienta de hallazgos

## Nombre

`findings_query`

## Principio de alcance

La herramienta se construye por turno con el `CaseScope` capturado en una clausura. El esquema
expuesto al modelo **no incluye** `case_id`, ni rutas, ni nombres de tabla, ni SQL. Aunque el
modelo envíe un `case_id`, el campo no existe y se rechaza o se ignora sin efecto.

La implementación usa el ORM con parámetros enlazados. No se construye SQL a partir de texto
generado.

## Argumentos

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "asset": { "type": "string", "maxLength": 120 },
    "severity": { "enum": ["Critical", "High", "Medium", "Low", "Info"] },
    "qid": { "type": "string", "pattern": "^[0-9]{1,10}$" },
    "cve": { "type": "string", "pattern": "^CVE-[0-9]{4}-[0-9]{4,7}$" },
    "group_by": { "enum": ["severity", "asset"] },
    "detail": { "type": "boolean" },
    "limit": { "type": "integer", "minimum": 1, "maximum": 100 }
  }
}
```

Todos los filtros son opcionales. Sin filtros, opera sobre todos los hallazgos del caso. `limit`
solo aplica a listas de detalle; los conteos no se limitan.

## Resultado

```json
{
  "total": 42,
  "groups": [
    { "key": "Critical", "count": 3 },
    { "key": "High", "count": 11 }
  ],
  "items": [
    {
      "finding_id": "...",
      "asset": "api-gateway",
      "title": "Componente desactualizado",
      "severity_label": "High",
      "severity_raw": "4",
      "cvss_base": 7.5,
      "qid": "12345",
      "cves": ["CVE-2024-0001"],
      "first_detected": "2026-01-10",
      "last_detected": "2026-02-01",
      "provenance": "synthetic:demo-findings-v1"
    }
  ],
  "dataset": {
    "name": "demo-findings-v1",
    "version": "1",
    "checksum": "…",
    "is_synthetic": true
  },
  "truncated": false
}
```

Reglas del resultado:

- `total` y `groups[].count` se calculan con `COUNT(*)` sobre exactamente los filtros aplicados.
- `items` solo se incluye cuando `detail=true`, limitado por `limit`.
- `truncated=true` cuando hay más elementos que `limit`; el conteo sigue siendo el real.
- `dataset.is_synthetic` siempre `true` en este incremento.
- El resultado expuesto al modelo **no contiene** `case_id`, rutas ni nombres de tabla. El servidor
  registra el caso autorizado en `run_tool_calls` para trazabilidad; el modelo nunca lo recibe.

## Errores

| `status` | `error_code` | Cuándo | Efecto en el turno |
|---|---|---|---|
| `invalid_arguments` | `invalid_severity` | Valor fuera del enum | El modelo recibe el error y puede corregir |
| `invalid_arguments` | `invalid_qid` | Formato incorrecto | Igual |
| `invalid_arguments` | `invalid_cve` | Formato incorrecto | Igual |
| `invalid_arguments` | `limit_out_of_range` | `limit` fuera de 1..100 | Igual |
| `error` | `tool_failed` | Fallo de base de datos | El turno termina en `failed` |
| `error` | `tool_timeout` | Excede el tiempo de la herramienta | El turno termina en `timeout` |

Un error de argumentos no inventa un resultado ni devuelve una lista vacía: devuelve el error.

## Registro

Cada invocación crea una fila en `run_tool_calls` con:

- `tool_name = "findings_query"`
- `origin = "model_requested"` (en este incremento la herramienta solo se ejecuta a solicitud del
  modelo; si en el futuro una ruta determinista la usa, se registra como `deterministic`)
- `arguments_json` (validado)
- `result_summary_json` (totales y grupos, sin filas completas)
- `status`, `error_code`, `duration_ms`

## Invariantes

1. La herramienta no puede leer un caso distinto del de la clausura.
2. No acepta SQL, nombres de tabla ni ordenamiento arbitrario.
3. Toda cifra mostrada al usuario proviene de esta herramienta y es recalculable.
4. Un caso sin hallazgos devuelve `total=0`, `groups=[]`, `items=[]`; nunca una cifra inventada.
5. Los hallazgos se presentan como datos educativos sintéticos, nunca como importación de Qualys.
6. Una pregunta sin resultados documentales puede seguir siendo respondida por esta herramienta: la
   recuperación vacía no cierra el turno. La ausencia de hallazgos tampoco se presenta como riesgo
   bajo.
