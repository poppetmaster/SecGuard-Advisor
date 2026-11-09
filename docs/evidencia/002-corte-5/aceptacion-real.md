# Aceptación real — 002 Qualys

Fecha de ejecución local: 2026-11-09.

## Insumos

- `../14-Qualys_Hallazgos_Active_New_ReOpened.csv` (CSV filtrado autorizado).
- `../14-Qualys_Hallazgos_Active_New_ReOpened_manifest.json`.
- Ollama local con `qwen3.5:9b` y `embeddinggemma`.
- Almacenamiento y bases SQLite en directorios temporales fuera de Git.
- No se abrió ni procesó el reporte original de 62 MB.

## Resultados observados

Validación con manifiesto (`manifest_status=matched`, `staged`):

| Métrica | Valor |
|---|---|
| Filas | 662 |
| Columnas detectadas | 41 |
| Active | 631 |
| New | 10 |
| Re-Opened | 21 |
| Fixed | 0 |
| Severidad 1 / 2 / 3 / 4 / 5 | 20 / 316 / 94 / 162 / 70 |
| Explotabilidad positiva / indeterminada | 129 / 533 |
| Malware positivo / indeterminado | 8 / 654 |
| Ambos positivos | 8 |
| Registros con múltiples CVE | 179 |
| Grupos de posibles repeticiones | 10 |
| Filas adicionales de repeticiones | 11 |

También se comprobó `manifest_status=absent` con el mismo CSV y `mismatch`/`invalid` con manifiestos
temporales modificados. El flujo HTTP formulario → validación → vista previa → confirmación → consulta
quedó confirmado, junto con idempotencia, aislamiento entre casos y un CVE compartido sin
multiplicación de filas.

## Conversación real con Ollama

Tres consultas reales sobre la instantánea importada, contrastadas con SQLite:

| Consulta | Resultado de la herramienta | SQLite |
|---|---|---|
| Total de registros | 662 | 662 |
| Severidad 5 | 70 | 70 |
| Prioridad conjunta (explotabilidad y malware) | 8 | 8 |

Las respuestas usaron la herramienta `findings_query`, conservaron la procedencia de la instantánea y
no generaron citas documentales ni `Results` completo.

## Separación entre tipos de prueba

- **Datos reales**: validación, flujo HTTP, SQLite, CVE múltiple y conversación Ollama.
- **Fixtures sintéticos**: `Fixed`, estado desconocido, indicadores indeterminados, prioridad
  combinada, cancelación, privacidad de HTML/trazas y los dos estados vacíos.
- **Ollama real**: solo la conversación de aceptación y los embeddings de la consulta.
- **Dobles**: pruebas rápidas de privacidad, aceptación de interfaz y presupuesto.

## Comandos y estado

```bash
LANGSMITH_TRACING=false uv run pytest tests/integration/test_qualys_import_real.py -q -s
# 1 passed

make check
# 409 passed, 35 deselected

LANGSMITH_TRACING=false make test-integration
# 34 passed, 1 skipped (LangSmith no configurado)
```

## Limitaciones

- LangSmith no está configurado en este entorno: el envío real de trazas queda skipped; la privacidad
  se comprobó con tracer y callbacks falsos, no con una cuenta externa.
- SC-001 y SC-003 de 001 siguen siendo validaciones humanas recomendadas y no ejecutadas.
- La CI remota no se ejecutó ni se declara aprobada.
