# Comparación de proveedores — Evaluación 005

Conjunto `005-evaluation-v1` congelado el 2026-11-23; hash `998dc34b889fd5455f56287fcbb1ca5430be33fac644f9a23c7ee04774a007bd`.

Resultados **exploratorios**: 10 escenarios por proveedor no alcanzan para una conclusión estadística. La calidad 0-2 es una evaluación asistida por IA, no una revisión humana independiente.

## Resumen por proveedor

| Proveedor | Ejecutados | Aprobados | Fallidos | Bloqueados | Tasa de éxito | Latencia mediana | Latencia media | Máxima |
|---|---|---|---|---|---|---|---|---|
| Ollama (`qwen3.5:9b`) | 10 | 6 | 4 | 0 | 60.00% | 38793 ms | 66896 ms | 182842 ms |
| DeepSeek (`deepseek-flash`) | 9 | 6 | 3 | 1 | 66.67% | 5541 ms | 6000 ms | 11792 ms |
| Anthropic (`claude-haiku-5-5`) | 9 | 4 | 5 | 1 | 44.44% | 7028 ms | 24879 ms | 85696 ms |

Latencia medida sobre las ejecuciones (los bloqueados no son llamadas completas). Medianas sin tiempos agotados: ollama 32463 ms, deepseek 5541 ms, anthropic 7028 ms.

## Tokens y costo

| Proveedor | Entrada | Salida | Caché | Costo total | Costo medio | Costos desconocidos |
|---|---|---|---|---|---|---|
| ollama | 33168 | 3664 | 0 | sin cobro por API | sin cobro por API | 0 |
| deepseek | 33371 | 2592 | 23296 | 0.006087 | 0.0008695714285714285714285714286 | 2 |
| anthropic | 49230 | 3602 | 0 | 0.005839 | 0.0009731666666666666666666666667 | 3 |

Ollama se ejecuta localmente: no hay cobro por API ni cuota comercial. No se declara costo operativo total cero.

## Calidad y validaciones automáticas

| Proveedor | Estructura | Citas válidas (respuestas con citas) | Consultas estructuradas | Abstención | Calidad IA 0-2 |
|---|---|---|---|---|---|
| ollama | 80.00% | 1 (4/4) | 1 (2 consultas) | 1/1 | 0.9 |
| deepseek | 77.78% | 1 (4/4) | 1 (1 consultas) | 1/1 | 1.13 |
| anthropic | 66.67% | 1 (3/3) | 1 (1 consultas) | 1/1 | 0.87 |

«Citas válidas» usa el validador del producto (`check_citation`, comparación normalizada) y exige cita resoluble. La columna `citations_byte_exact` de `metricas.csv` es más estricta (igualdad byte a byte) y no representa un fallo.

## Detalle por escenario

### Ollama (`qwen3.5:9b`)

| Escenario | Resultado | Salida | Error | Citas (válidas/emitidas) | Fuente esperada | Coincidencia SQL | ms | Costo |
|---|---|---|---|---|---|---|---|---|
| S01 CSF 2.0 | approved | answered | — | 8/8 | True | — | 76614 | — |
| S02 AI RMF | failed | error | run_timeout | 0/0 | False | — | 136618 | — |
| S03 OWASP LLM | failed | answered | — | 3/3 | True | — | 97772 | — |
| S04 Fuentes públicas combinadas | failed | error | run_timeout | 0/0 | False | — | 182842 | — |
| S05 Política ficticia | approved | answered | — | 2/2 | True | — | 35284 | — |
| S06 Seguimiento de S05 | approved | answered | — | 1/1 | True | — | 21468 | — |
| S07 Hallazgos sintéticos por activo | approved | answered | — | 0/0 | True | True | 26462 | — |
| S08 Hallazgos importados (severidad/explotabilidad) | approved | answered | — | 0/0 | True | True | 29642 | — |
| S09 Abstención | approved | insufficient_evidence | — | 0/0 | True | — | 19957 | — |
| S10 Informe breve | failed | insufficient_evidence | — | 0/0 | False | — | 42303 | — |

### DeepSeek (`deepseek-flash`)

| Escenario | Resultado | Salida | Error | Citas (válidas/emitidas) | Fuente esperada | Coincidencia SQL | ms | Costo |
|---|---|---|---|---|---|---|---|---|
| S01 CSF 2.0 | approved | answered | — | 5/5 | True | — | 5541 | 0.001693 |
| S02 AI RMF | approved | answered | — | 6/6 | True | — | 7349 | 0.001882 |
| S03 OWASP LLM | failed | error | invalid_model_output | 0/0 | False | — | 11792 | — |
| S04 Fuentes públicas combinadas | failed | error | invalid_model_output | 0/0 | False | — | 9238 | — |
| S05 Política ficticia | approved | answered | — | 2/2 | True | — | 3254 | 0.000450 |
| S06 Seguimiento de S05 | approved | answered | — | 1/1 | True | — | 3031 | 0.000413 |
| S07 Hallazgos sintéticos por activo | approved | answered | — | 0/0 | True | True | 5623 | 0.000847 |
| S08 Hallazgos importados (severidad/explotabilidad) | blocked | error | external_tool_blocked | 0/0 | True | — | 982 | 0.000114 |
| S09 Abstención | approved | insufficient_evidence | — | 0/0 | True | — | 2946 | 0.000266 |
| S10 Informe breve | failed | insufficient_evidence | — | 0/0 | False | — | 5232 | 0.000536 |

### Anthropic (`claude-haiku-5-5`)

| Escenario | Resultado | Salida | Error | Citas (válidas/emitidas) | Fuente esperada | Coincidencia SQL | ms | Costo |
|---|---|---|---|---|---|---|---|---|
| S01 CSF 2.0 | approved | answered | — | 2/2 | True | — | 37050 | 0.001574 |
| S02 AI RMF | failed | error | invalid_model_output | 0/0 | False | — | 7385 | — |
| S03 OWASP LLM | failed | error | invalid_model_output | 0/0 | False | — | 6984 | — |
| S04 Fuentes públicas combinadas | failed | error | invalid_model_output | 0/0 | False | — | 7028 | — |
| S05 Política ficticia | approved | answered | — | 2/2 | True | — | 68692 | 0.000689 |
| S06 Seguimiento de S05 | approved | answered | — | 1/1 | True | — | 4308 | 0.000775 |
| S07 Hallazgos sintéticos por activo | failed | insufficient_evidence | — | 0/0 | True | True | 85696 | 0.001459 |
| S08 Hallazgos importados (severidad/explotabilidad) | blocked | error | external_tool_blocked | 0/0 | True | — | 1265 | 0.000311 |
| S09 Abstención | approved | insufficient_evidence | — | 0/0 | True | — | 3094 | 0.000640 |
| S10 Informe breve | failed | insufficient_evidence | — | 0/0 | False | — | 3680 | 0.000702 |

## Presupuesto

- Presupuesto global: 5 USD; por turno: 5 USD; tarifas `2026-11-22`.
- Estimación previa: {"deepseek": "0.052800", "anthropic": "0.020000"}.
- Ledger liquidado: 0.025515 USD; uso observado: 0.013423 USD.
- Restante conservador (ledger): 4.974485 USD.

## Limitaciones

- 10 escenarios por proveedor: muestra pequeña y exploratoria.
- Sin evaluación semántica humana independiente; la calidad 0-2 es asistida por IA.
- Corpus público y caso ficticio; no se usaron datos privados ni Qualys real.
- Las llamadas externas se hicieron con proveedores reales; DeepSeek y Anthropic no exponen una versión de API en las respuestas registradas.
- Los proveedores externos bloquean `findings_query` sobre datos importados (`external_tool_blocked`); S08 se registra como bloqueado, no como fallo.

## Historial de iteraciones

- `iteracion-1/`: primera pasada; el arnés exigía `source_id` en documentos de caso y limitaba la salida externa a 512 tokens. Conservada como evidencia.
- `iteracion-2/`: segunda pasada con la coincidencia de fuentes corregida a mitad de la corrida; conservada como evidencia.
- Raíz del directorio: tercera pasada, declarada como resultado de la evaluación.
