# Evaluación funcional 005 — comparación de proveedores

**Fecha de ejecución**: 2026-11-23 (America/Bogota, `-05`)
**Rama**: `005-generador-configurable`
**Conjunto congelado**: `005-evaluation-v1`, 2026-11-23
**Hash del conjunto**: `998dc34b889fd5455f56287fcbb1ca5430be33fac644f9a23c7ee04774a007bd`

Resultados **exploratorios**: diez escenarios por proveedor no alcanzan para una conclusión
estadística. No se declara aceptación de proveedores externos ni superioridad definitiva de uno
sobre otro.

## Alcance

Se evaluó el recorrido real de consulta documental y de hallazgos de 005 con tres generadores:

| Proveedor | Modelo | Identidad registrada |
|---|---|---|
| Ollama local | `qwen3.5:9b` | digest `56671c2a…3c90` en todas las ejecuciones |
| DeepSeek | `deepseek-flash` | `deepseek-flash` (S02–S10); S01 sin identidad informada por el proveedor |
| Anthropic | `claude-haiku-5-5` | `claude-haiku-5-5` (S02–S10); S01 sin identidad informada por el proveedor |

Los proveedores externos no exponen una versión de API en las respuestas registradas; no se inventa
ese dato. Cada fila de `resultados.json` conserva `provider`, `model`, `identity`, `run_id` y los
pasos de modelo con su duración.

## Instancia aislada

- Almacenamiento temporal (`mktemp -d`), SQLite y checkpoints propios, eliminados al terminar.
- Instancia Qdrant única por corrida (`instance_id` propio), sin tocar `storage/` del proyecto.
- Corpus público oficial ingerido con `ingest_public_corpus` (CSF 2.0, AI RMF, OWASP LLM Top 10 y
  documento combinado), idéntico para los tres proveedores.
- Caso ficticio con tres documentos ficticios (respaldo, accesos y parches) y seis hallazgos
  sintéticos. No se usó el CSV Qualys privado, activos reales, IP, documentos ni conversaciones del
  usuario.
- Para S08 se importó `tests/fixtures/files/qualys_synthetic_valid.csv` (fixture sintético) en el
  caso ficticio.
- `LANGSMITH_TRACING=false`; no se envió nada a Telegram ni por correo; no se publicó nada.
- No se aumentaron presupuestos ni se modificó `.env`. Las claves externas no se muestran en este
  directorio.

## Conjunto congelado de diez escenarios

| ID | Tipo | Pregunta | Hechos esperados | Fuente o SQL de referencia | Criterio de aprobación |
|---|---|---|---|---|---|
| S01 | CSF 2.0 | ¿Cuáles son las seis funciones centrales del NIST Cybersecurity Framework 2.0? | Govern, Identify, Protect, Detect, Respond, Recover | corpus público CSF | responde, cita resoluble, seis funciones |
| S02 | AI RMF | ¿Cuáles son las funciones centrales del NIST AI Risk Management Framework? | Govern, Map, Measure, Manage | corpus público AI RMF | responde, cita resoluble, cuatro funciones |
| S03 | OWASP LLM | ¿Qué riesgos de aplicaciones con LLM describe OWASP y qué controles recomienda? Mencioná al menos dos riesgos y una recomendación. | prompt injection, información sensible, cadena de suministro | corpus público OWASP LLM | responde, cita resoluble, dos riesgos y una recomendación |
| S04 | Fuentes combinadas | ¿Cómo se relacionan las funciones del NIST CSF 2.0 con las del NIST AI RMF para gobernar riesgos de IA? Citá ambas fuentes. | Govern, Identify, Map, Measure, Manage | CSF 2.0 + AI RMF | responde, citas de ambas fuentes |
| S05 | Política ficticia | ¿Cada cuánto se prueba la restauración del respaldo y quién conserva el registro? | trimestral, responsable de infraestructura, registro | «Política de respaldo» | responde, cita de la política, ambos hechos |
| S06 | Seguimiento de S05 | ¿Qué se conserva de cada prueba de restauración? | registro, prueba | «Política de respaldo»; misma conversación que S05 | responde con el contexto de S05 y cita resoluble |
| S07 | Hallazgos sintéticos | ¿Cuántos hallazgos High hay por activo en el caso? | total 3; api-gateway 2, customer-portal 1 | `findings` con `severity_label='High'` agrupado por `Asset.name` | responde, herramienta correcta, total y grupos coinciden con SQLite |
| S08 | Hallazgos importados | ¿Cuántos registros importados tienen severidad 5 y explotabilidad positiva, agrupados por activo? | total 1; asset-1.example 1 | `qualys_vulnerabilities` con `severity_level=5`, `exploitability_eval='positive'`, `status_group='pending_known'` agrupado por `asset_label` | Ollama: herramienta correcta y coincidencia; externos: bloqueo por política |
| S09 | Abstención | ¿Cuál es la capital de Francia? | abstención explícita | sin fuente en corpus ni caso | se abstiene y no inventa citas |
| S10 | Informe breve | Prepará un informe breve sobre los controles de respaldo y acceso del caso: resumen, evidencias, tres recomendaciones ordenadas y limitaciones. | respaldo, acceso, recomendación, limitación | «Política de respaldo» y «Gestión de accesos» | estructura válida, al menos una cita, recomendaciones y limitaciones |

La relación S05→S06 es explícita: S06 reutiliza el mismo caso y la misma conversación que S05, sin
crear un caso nuevo. El resto de los escenarios usa conversaciones independientes. No se usó la
salida de un modelo como verdad de referencia; los valores esperados de S07 y S08 se calcularon en
SQLite antes de llamar a los modelos y quedaron en `casos.json`.

Las preguntas, hechos esperados y criterios están congelados en
`tests/fixtures/evaluation_005.py`. No se ajustaron casos ni umbrales después de observar
resultados.

## Ejecución

```bash
uv run python scripts/evaluate_providers_005.py \
  --output-dir docs/evidencia/005-evaluacion-proveedores \
  --providers ollama,deepseek,anthropic
```

- Los escenarios se ejecutaron en secuencia, primero todos los de un proveedor y luego el siguiente.
- Cada proveedor usó el mismo corpus, los mismos documentos ficticios, la misma recuperación y las
  mismas preguntas.
- Sin fallback: un proveedor no sustituye la respuesta de otro.
- Perfil efectivo por turno: Ollama con salida automática de 1200 tokens dentro de 8192 de contexto;
  DeepSeek y Anthropic con máximo de salida 1200 y 90 s por llamada. Ollama usa temperatura 0.1;
  DeepSeek no envía temperatura; Anthropic omite temperatura. La diferencia se documenta y no se
  normaliza.
- Autorización externa por caso (`fictional_case`) y presupuestos existentes: 5 USD global y 5 USD
  por turno.
- Reintentos del turno: 1 intento por escenario, sin reintentos manuales; la métrica
  `turn_attempts` es 1 por diseño del ejecutor. Reparaciones internas registradas: 0 en los treinta
  escenarios.

## Resultados

### Consumo completo por proveedor

Incluye todos los escenarios e intentos registrados, también los bloqueados. El costo es un
**subtotal conocido**, no facturación completa; los registros desconocidos no se presentan como cero.

| Proveedor | Registros | Bloqueados | Tokens E | Tokens S | Caché | Costo conocido | Cobertura | Conocidos / desconocidos / N/A |
|---|---|---|---|---|---|---|---|---|
| Ollama `qwen3.5:9b` | 10 | 0 | 33 168 | 3 664 | 0 | sin cobro por API | — | 0 / 0 / 10 |
| DeepSeek `deepseek-flash` | 10 | 1 | 34 998 | 2 625 | 24 704 | 0,006201 USD | 80,00 % (8/10) | 8 / 2 / 0 |
| Anthropic `claude-haiku-5-5` | 10 | 1 | 52 076 | 3 654 | 0 | 0,006150 USD | 70,00 % (7/10) | 7 / 3 / 0 |

- DeepSeek incluye 0,000114 USD de S08 bloqueado; Anthropic incluye 0,000311 USD de S08 bloqueado.
- Un bloqueo posterior a una llamada no elimina su consumo.
- Ollama se ejecuta localmente: no hay cobro por API ni cuota comercial; no se declara costo
  operativo total cero.
- Las llamadas externas sin uso devuelto quedan como costo desconocido, no como cero.

### Comparativo funcional — muestra común

Muestra común ejecutada: **9 escenarios** (S01, S02, S03, S04, S05, S06, S07, S09, S10). Éxito,
latencia y calidad se recalculan solo sobre esta intersección; los bloqueos y fallos siguen en la
matriz completa.

| Proveedor | Muestra | Aprobados | Fallidos | Éxito | Latencia mediana | Estructura | Citas válidas | Herramientas | Abstención | Calidad IA |
|---|---|---|---|---|---|---|---|---|---|---|
| Ollama | 9 | 5 | 4 | 5/9 (55,56 %) | 42 303 ms (n=9) | 77,78 % | 100 % (4/4) | 100 % (n=1) | 1/1 | 0,87 (n=9) |
| DeepSeek | 9 | 6 | 3 | 6/9 (66,67 %) | 5 541 ms (n=9) | 77,78 % | 100 % (4/4) | 100 % (n=1) | 1/1 | 1,13 (n=9) |
| Anthropic | 9 | 4 | 5 | 4/9 (44,44 %) | 7 028 ms (n=9) | 66,67 % | 100 % (3/3) | 100 % (n=1) | 1/1 | 0,87 (n=9) |

«Citas válidas» usa el validador del producto (`check_citation`, comparación normalizada) y exige
cita resoluble. No prueba respaldo semántico. La columna `citations_byte_exact` de `metricas.csv` es
más estricta y no representa un fallo.

La calidad 0-2 es asistida por IA, no una revisión humana independiente. No se declara un ganador.

### Detalle por escenario

| Escenario | Ollama | DeepSeek | Anthropic |
|---|---|---|---|
| S01 CSF 2.0 | aprobado | aprobado | aprobado |
| S02 AI RMF | fallido (timeout) | aprobado | fallido (`invalid_model_output`) |
| S03 OWASP LLM | fallido (faltan riesgos esperados) | fallido (`invalid_model_output`) | fallido (`invalid_model_output`) |
| S04 Fuentes combinadas | fallido (timeout) | fallido (`invalid_model_output`) | fallido (`invalid_model_output`) |
| S05 Política ficticia | aprobado | aprobado | aprobado |
| S06 Seguimiento | aprobado | aprobado | aprobado |
| S07 Hallazgos sintéticos | aprobado (3; 2+1) | aprobado (3; 2+1) | fallido (consulta correcta, respuesta insuficiente) |
| S08 Hallazgos importados | aprobado (1; 1) | bloqueado (`external_tool_blocked`) | bloqueado (`external_tool_blocked`) |
| S09 Abstención | aprobado | aprobado | aprobado |
| S10 Informe breve | fallido (abstención) | fallido (abstención) | fallido (abstención) |

El detalle completo, con `run_id`, tiempos por paso, tokens, costo, citas y errores, está en
`metricas.csv` y `resultados.json`.

## Validación de interfaz con Playwright

Instancia separada (`SECGUARD_STORAGE_DIR` temporal, instancia Qdrant propia, corpus público), con
Ollama como proveedor activo:

- Se abrió **Administración → Configuración de IA** en `/settings/ai`.
- Se guardaron los tres perfiles: Ollama `qwen3.5:9b`, DeepSeek `deepseek-flash` y Anthropic
  `claude-haiku-5-5`; cada guardado mostró «Configuración guardada» y actualizó el panel
  «Configuración activa».
- Los tres perfiles quedaron persistidos de forma independiente en SQLite; cambiar uno no reescribió
  los otros.
- Se creó el caso ficticio «Evaluación UI 005» y se ejecutó S01 desde el formulario real.
- Durante la ejecución se observaron el indicador «Consultando las fuentes y preparando la
  respuesta…» y el botón «Preguntar» deshabilitado (`ui-loading.png`).
- La respuesta mostró dos citas con «Control automático (existencia y cita literal): válida» y el
  aviso de que el respaldo semántico queda pendiente de revisión humana (`ui-ollama-s01.png`).
- «Ver ejecución» abrió `/cases/…/runs/307674cce8b047efa6fa56ad685a6933` y registró
  `ollama` / `qwen3.5:9b`, identidad `56671c2a…3c90`, estado `succeeded`, salida `answered`,
  27 799 ms, 4 883 tokens de entrada, 260 de salida, costo `not_applicable` y dos citas válidas
  (`ui-ejecucion-ollama.png`).
- No hubo errores ni advertencias de consola. El HTML del formulario, de la consulta y de la
  ejecución no contiene claves; el panel solo informa «Clave configurada».
- Las capturas usan únicamente datos públicos o ficticios.

La ejecución de interfaz es una validación del recorrido y **no se suma** a los treinta escenarios
comparados: es Ollama y no duplica llamadas pagadas.

## Hallazgos y defectos

1. **Parseo de salida estructurada externa (corregido).** DeepSeek y Anthropic devolvieron JSON
   envuelto en bloque de código o con texto alrededor, y el adaptador lo rechazaba como
   `invalid_model_output`. Se ajustó `parse_structured` en
   `src/secguard_advisor/conversation/providers/http_common.py` para aceptar bloque cercado y texto
   circundante, con regresión en `tests/unit/test_http_common.py` (5 pruebas). Es un defecto que
   bloqueaba la evaluación externa.
2. **Límite de salida externo (corregido en el arnés).** La primera pasada usó 512 tokens de salida
   y truncó respuestas externas; las pasadas 2 y 3 usaron 1200. La pasada 1 se conserva en
   `iteracion-1/`.
3. **Timeout de Ollama por encima de los límites declarados (pendiente).** S02 registró un paso de
   agente de 136 618 ms y S04 de 182 842 ms, por encima de los 90 s por llamada y 120 s por turno.
   No bloqueó la evaluación, pero contradice el límite documentado y queda como defecto a corregir.
4. **Calidad desigual por escenario (sin corregir).** Ollama respondió S03 sin los riesgos
   esperados y se abstuvo en S10; DeepSeek y Anthropic fallaron S02–S04 por salida estructurada
   inválida; Anthropic ejecutó bien la consulta de S07 pero no sostuvo la respuesta. Se preservan
   como fallos, sin sustituir respuestas.
5. **Bloqueo de datos importados (esperado).** DeepSeek y Anthropic devolvieron
   `external_tool_blocked` en S08. Se registra como bloqueado, no como fallo.
6. **Costo desconocido en llamadas externas fallidas (esperado).** Sin uso devuelto por el
   proveedor, el costo queda `unknown`; no se estima a partir de tokens inventados.

## Presupuesto

- Límites existentes: 5 USD global y 5 USD por turno; tarifas `2026-11-22`.
- Estimación previa: DeepSeek 0,052800 USD; Anthropic 0,020000 USD.
- Ledger liquidado acumulado de las tres pasadas: 0,025515 USD.
- Uso observado acumulado: 0,013423 USD.
- Restante conservador según ledger: **4,974485 USD**.
- No se aumentó ningún presupuesto ni se modificó `.env`.

## Limitaciones

- Diez escenarios por proveedor: muestra pequeña y exploratoria; no prueba superioridad estadística.
- Sin evaluación semántica humana independiente. La calidad 0–2 es una heurística asistida por IA,
  no una revisión humana.
- Ollama depende del hardware local; su latencia no es comparable con la de una API.
- DeepSeek y Anthropic no informaron versión de API; solo se registra el modelo y la identidad
  disponible.
- Los límites de salida difieren entre pasadas (512 en `iteracion-1/`, 1200 en las pasadas 2 y 3) y
  entre proveedores; se documenta en lugar de normalizarse.
- SC-001 (recorrido humano cronometrado) y SC-003 (diez revisiones semánticas) no se ejecutaron; la
  revisión en otros navegadores sigue pendiente.
- No se evaluaron Telegram, correo, Qdrant alternativo ni entrenamiento; quedan fuera de alcance.

## Artefactos

- `README.md`: este documento.
- `casos.json`: conjunto congelado, hash, valores esperados de S07/S08, presupuesto y estimaciones.
- `resultados.json`: treinta filas con métricas por escenario.
- `metricas.csv`: tabla plana para análisis.
- `comparacion-proveedores.md`: informe comparativo.
- `resumen.json`: agregados por proveedor.
- `ui-loading.png`, `ui-ollama-s01.png`, `ui-ejecucion-ollama.png`,
  `ui-configuracion-ollama.png`, `ui-configuracion-deepseek.png`,
  `ui-configuracion-anthropic.png`: capturas con datos públicos o ficticios.
- `iteracion-1/`, `iteracion-2/`: pasadas previas conservadas con sus fallos.

## Reproducción

```bash
uv run python scripts/evaluate_providers_005.py \
  --output-dir docs/evidencia/005-evaluacion-proveedores \
  --providers ollama,deepseek,anthropic
uv run python scripts/report_evaluation_005.py \
  --output-dir docs/evidencia/005-evaluacion-proveedores
uv run pytest tests/unit/test_http_common.py -q
```

La evaluación real requiere Ollama, Qdrant, corpus público y las claves externas en `.env`. Sin
claves o sin presupuesto, los proveedores externos se marcan como bloqueados; no se sustituyen por
simulaciones.
