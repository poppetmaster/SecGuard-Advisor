# 005 — Último resultado (evaluación real completada; aceptación externa pendiente)

**Fecha**: 2026-11-23 (America/Bogota, `-05`) — actualizado tras la evaluación real
**Rama**: `005-generador-configurable`
**Estado**: T001–T038, T040–T042 y T043–T048 completadas; R1–R3 corregidos. La comparación externa
real se ejecutó y T039 queda **parcialmente acreditada**: falta el marker `external` de pytest.
**005 no tiene aceptación de proveedores externos**: la calidad observada no lo permite.

## Dictamen

R1–R3 están corregidos y acreditados con pruebas. La comparación local con Ollama real se ejecutó
sobre un conjunto congelado de diez preguntas ficticias: 8/8 citas esperadas, 2/2 abstenciones y una
latencia media de 13948 ms. La comparación DeepSeek/Anthropic se ejecutó solo con transporte simulado.
La comparación externa real no se ejecutó porque no hay presupuesto aprobado ni credenciales; no se
usan valores de ejemplo como aprobación.

## R1 — Reintento externo

- `start_retry_turn` comparte con el inicio `resolve_turn_profile`, `create_turn_record` y
  `build_turn_context`.
- Autorización vigente comprobada antes de cualquier conteo remoto o llamada.
- Ausente/revocada bloquea; no se hereda ni amplía.
- `external_scope` y `external_authorization_id` llegan al contexto y a `runs`.
- `public_corpus` excluye contexto del caso, historial y fuentes privadas.
- `findings_query` importado sigue bloqueado.
- El intento nuevo registra proveedor, modelo, identidad y parámetros efectivos; conserva pregunta,
  `attempt_no` y `retry_of_run_id`.

Evidencia: `tests/unit/test_retry_external_scope.py` — **6 passed** (cero llamadas sin autorización,
señuelos privados, cambio local→externo, importados bloqueados, vista).

## R2 — Timeout por llamada

- `post_json` aplica `timeout_seconds` a `client.post`.
- DeepSeek y Anthropic lo propagan; el nodo lo acota por perfil y tiempo restante.
- Pruebas con cliente 12,5 s y llamada 0,25 s confirman `read=0.25`.
- Sin reintentos implícitos; timeout conserva la reserva.

## R3 — Evidencia efectiva

- Inicio y reintento persisten salida máxima, timeout, autorización, proveedor, modelo e identidad
  desde el mismo perfil.
- Prueba integral con **64 tokens** y **12.5 s**: SQLite y la vista muestran esos valores.
- Las ejecuciones históricas conservan 1200/90; no se reescriben.

## Comparación (T035–T038)

- Conjunto congelado en `tests/fixtures/provider_comparison.py`; hash
  `92778d5cdffca49c065354a4c5e816d8af678c30ae795d5fd506ffe8db5c5129`; 10 preguntas (8 con cita
  esperada, 2 de abstención).
- Ejecutor `scripts/compare_providers.py` con JSON/Markdown.
- Pruebas del conjunto y ejecutor: `tests/unit/test_provider_comparison.py` — **4 passed**.

### Ollama real

`docs/evidencia/005-comparacion/ollama.json` y `ollama.md`:

```text
transporte: real
modelo: qwen3.5:9b
recuperación: ollama-embeddinggemma
turnos: 10
respondidas: 8
citas totales: 8
citas esperadas acertadas: 8/8
abstenciones esperadas/observadas: 2/2
latencia media del turno: 13948 ms
costo de API: no aplicable (Ollama local)
evaluación semántica: no realizada
```

Duraciones: 6929, 7738, 6816, 8008, 8114, 9666, 10216, 16992, 25881 y 39123 ms.
Recomendaciones declaradas: 1. `missing_info` declarados: 2.

### DeepSeek/Anthropic simulados

- `deepseek-mock.json` / `.md`: 10 turnos, costo calculado simulado 0.000810 USD.
- `anthropic-mock.json` / `.md`: 10 turnos, costo calculado simulado 0.000600 USD.
- No son mediciones reales; no acreditan calidad ni latencia de los proveedores.

### T039 real

Pendiente: `deepseek-real-pending.json` y `anthropic-real-pending.json` registran «Sin presupuesto
externo aprobado (external_budget_usd=0)». No se usaron claves ni se hizo ninguna llamada paga.

## T040 — Regresión

```text
make check
  → 649 passed, 37 deselected, 17 warnings

make test-integration
  → 37 passed, 649 deselected, 14 warnings (1213.60 s = 20:13)
```

La primera ejecución de integración falló en `test_qualys_import_real` porque el prompt de decisión
no repetía una consulta con filtro distinto; se corrigió (`decide-v6`), la prueba pasó y la suite
completa quedó verde. No se relajaron criterios ni se ampliaron tiempos.

## T042 — Aceptación

**Aceptación local parcial**: Ollama real, comparación local, R1–R3, `make check` y
`make test-integration` verdes. **Proveedores externos no aceptados**: solo contratos simulados;
T039 real pendiente. T042 registra aceptación parcial, no integral.



## Configuración de IA desde la interfaz (T043–T048)

- Ruta `/settings/ai`, en el grupo **Administración** del menú general, fuera de un caso y disponible en escritorio y móvil. El grupo no implica autenticación ni roles.
- Selección de proveedor, modelo, máximo de salida (solo externos) y timeout; guardado en SQLite mediante
  `ai_configuration` y `ai_provider_profiles` (migración `f7a8b9c0d1e2`).
- Precedencia: configuración guardada > `Settings`/`.env`; `.env` conserva claves, endpoints y
  presupuestos y no se modifica. `SECGUARD_GENERATION_MODEL` vacío usa el modelo predeterminado.
- Perfiles independientes por proveedor; cambiar de proveedor no arrastra modelos ni sobrescribe
  parámetros de otro.
- Ollama no exige clave ni presupuesto monetario; su reserva de salida es automática dentro del
  contexto técnico y se muestra «Ejecución local; sin cobro por tokens de API». No se afirma costo
  operativo cero.
- Los límites externos se validan contra el proveedor/modelo seleccionado; cambiar de proveedor no
  arrastra modelos ni altera consultas en curso.
- Cada turno usa una instantánea; una consulta en curso conserva su perfil. Los reintentos usan la
  autorización vigente y registran los parámetros efectivos.
- Los recursos propios del turno (generador, contador, embeddings e índice) se cierran en éxito,
  error y fallo de preparación; no se cierran recursos inyectados o compartidos.
- El formulario muestra presupuestos global/por turno, moneda y «Clave configurada»/«Clave
  pendiente»; nunca valores, fragmentos ni máscaras. Conexión: «No verificada».
- Un externo con presupuesto cero muestra «Configurado; consultas externas bloqueadas hasta
  autorizar presupuesto». Guardar no autoriza gasto ni envía datos.
- No hay llamadas externas ni conteo remoto al abrir o guardar.

Pruebas nuevas: `tests/unit/test_ai_config_service.py` (9), `tests/contract/test_ai_settings_routes.py`
(12) y `tests/unit/test_ai_config_turn.py` (4); cierre de recursos (3). Playwright validó escritorio y móvil, guardado,
cambio de perfiles, mensajes, foco, Escape, ausencia de overflow y consola sin errores. Capturas en
`docs/evidencia/005-configuracion-ui/`.

`make check`: **677 passed**, 37 deselected.

## Limitaciones

- Evaluación semántica no realizada; solo comprobaciones automáticas.
- Corpus de comparación ficticio; no representa datos del usuario.
- Ollama: costo de API no aplicable; no se declara costo operativo total cero.
- Sin llamadas reales a DeepSeek/Anthropic en la comparación del 2026-11-22 (ver evaluación real
  del 2026-11-23).
- La configuración guardada no verifica la conexión; solo declara credencial presente.
- No se enviaron Qualys, derivados ni datos privados.
- `storage/`, `storage/demo`, Chroma y Qdrant sin cambios.
- `LANGSMITH_TRACING=false`.

## Archivos cambiados

```text
src/secguard_advisor/conversation/turn.py
src/secguard_advisor/conversation/retry.py
src/secguard_advisor/conversation/providers/http_common.py
src/secguard_advisor/conversation/providers/deepseek.py
src/secguard_advisor/conversation/providers/anthropic.py
src/secguard_advisor/conversation/prompts.py
src/secguard_advisor/conversation/nodes.py
tests/unit/test_retry_external_scope.py
tests/contract/test_deepseek_adapter.py
tests/contract/test_anthropic_adapter.py
tests/fixtures/provider_comparison.py
tests/unit/test_provider_comparison.py
scripts/compare_providers.py
docs/evidencia/005-comparacion/*.json
docs/evidencia/005-comparacion/*.md
```

## Commits

Ver `git log --oneline` en `005-generador-configurable`.

## Evaluación real de proveedores (2026-11-23)

Ejecutada sobre una instancia temporal, corpus público oficial y caso ficticio, con el conjunto
congelado `005-evaluation-v1`
(`998dc34b889fd5455f56287fcbb1ca5430be33fac644f9a23c7ee04774a007bd`). Evidencia completa en
`docs/evidencia/005-evaluacion-proveedores/`.

| Proveedor | Ejecutados | Aprobados | Fallidos | Bloqueados | Éxito | Mediana | Costo conocido |
|---|---|---|---|---|---|---|---|
| Ollama `qwen3.5:9b` | 10 | 6 | 4 | 0 | 60,0 % | 38 793 ms | sin cobro por API |
| DeepSeek `deepseek-flash` | 9 | 6 | 3 | 1 | 66,7 % | 5 541 ms | 0,006201 USD (incluye S08) |
| Anthropic `claude-haiku-5-5` | 9 | 4 | 5 | 1 | 44,4 % | 7 028 ms | 0,006150 USD (incluye S08) |

- S08 quedó bloqueado en los externos por `external_tool_blocked`; es el comportamiento esperado,
  no un fallo.
- Ollama agotó el tiempo en S02 (136 618 ms) y S04 (182 842 ms), por encima de 90 s por llamada y
  120 s por turno. Defecto registrado y pendiente.
- DeepSeek falló S03, S04 y S10; Anthropic falló S02, S03, S04, S07 y S10 por salida estructurada
  inválida, abstención o respuesta no sostenida; se conservan como fallos.
- Se corrigió `parse_structured` para aceptar JSON envuelto en bloque cercado o con texto alrededor,
  con regresión en `tests/unit/test_http_common.py` (5 pruebas). Bloqueaba la evaluación externa.
- Presupuesto estimado antes de llamar: DeepSeek 0,052800 USD y Anthropic 0,020000 USD. Ledger
  acumulado de las tres pasadas: 0,025515 USD; uso observado: 0,013423 USD; restante conservador
  **4,974485 USD**. No se aumentaron presupuestos.
- Playwright validó `/settings/ai` con los tres perfiles guardados y una ejecución real de S01 con
  Ollama; la página de ejecución registró `ollama` / `qwen3.5:9b`, dos citas válidas y sin errores de
  consola. Capturas en el directorio de evidencia.
- Las pasadas 1 y 2 se conservan en `iteracion-1/` e `iteracion-2/`; la raíz contiene la pasada
  declarada.

**T039**: la comparación externa real está ejecutada y registrada; el criterio de marcar pruebas
`external` en pytest y omitirlas sin credencial **no** está implementado, por lo que T039 no se
cierra. La aceptación externa sigue pendiente y no se declara.

## Panel «Uso y comparativos de IA» (2026-11-23)

- Ruta `/settings/ai/usage`, en **Administración** debajo de Configuración de IA, fuera de un caso.
- Persistencia aditiva: `ai_requests` (una fila por intento lógico), `ai_evaluations` y
  `ai_evaluation_results`. Migración `a3c4d5e6f7a8`; no se reescribieron ejecuciones.
- Instrumentación única en `provider_call`: reutiliza `runs`, `provider_usage` y
  `provider_budget_ledger`; registra operación, estado, duración, tokens, caché, razonamiento,
  fuente de uso, costo calculado, tarifa histórica y vínculo de evaluación. Sin claves, prompts ni
  respuestas.
- Tarjetas, gráficas interactivas con tabla accesible, tabla por proveedor/modelo, detalle paginado con enlace
  a la ejecución y cobertura observada/estimada/no disponible. Reservas pendientes e inciertas se
  muestran aparte del gasto calculado.
- Comparativo de pruebas con importación idempotente del informe 005
  (`make import-evaluation`); escenarios comunes, muestra incompleta, métricas automáticas, calidad
  asistida por IA y revisión humana registrada.
- Las ejecuciones sin telemetría se agregan desde `runs` y se marcan como histórico incompleto; los
  agregados importados no fabrican solicitudes.
- Pruebas: `make check` con **717 passed**, 37 deselected; integraciones afectadas **8 passed**.
  Evidencia y capturas en `docs/evidencia/005-panel-uso-ia/`.
- Ver y filtrar no invoca modelos ni gasta. No se añadieron botones para lanzar evaluaciones.

## Corrección de exactitud del panel de uso (2026-11-23)

- El comparativo separa **consumo completo** (todos los escenarios e intentos, incluidos los
  bloqueados) del **comparativo funcional** sobre la muestra común ejecutada.
- Costo conocido: DeepSeek **0,006201 USD** (incluye 0,000114 de S08 bloqueado) y Anthropic
  **0,006150 USD** (incluye 0,000311 de S08 bloqueado). Son subtotales conocidos: DeepSeek tiene 2
  registros con costo desconocido y Anthropic 3; no se presentan como factura completa.
- La muestra común ejecutada es de **9 escenarios** (S01–S07, S09, S10). Éxito funcional: Ollama
  5/9, DeepSeek 6/9, Anthropic 4/9. Latencia y calidad se recalculan sobre esa muestra. La matriz
  completa conserva S08 bloqueado y el resto de fallos.
- Los adaptadores DeepSeek y Anthropic capturan el uso antes de validar el esquema y reinician
  `last_usage` por llamada. `provider_call` conserva tokens y costo cuando la respuesta informó uso
  aunque el JSON sea inválido; sin evidencia mantiene costo desconocido y la reserva conservadora.
- Informes regenerados desde los resultados existentes, sin repetir la evaluación pagada:
  `docs/evidencia/005-evaluacion-proveedores/comparacion-proveedores.md`, `resumen.json` y
  `metricas.csv`.
- Evidencia y capturas actualizadas en `docs/evidencia/005-panel-uso-ia/`.

**Pendiente, no resuelto por esta corrección**: T039 (marker `external` de pytest), tiempos
excedidos de Ollama (S02 136 618 ms; S04 182 842 ms), errores de salida estructurada externa y el
informe breve S10.

## Gráficas interactivas del panel de uso (2026-11-23)

- Apache ECharts **5.6.0** (Apache-2.0) instalado con npm, copiado a `static/js/echarts.min.js` por
  `npm run copy:vendor` y registrado en `static/vendor/MANIFEST.md`. Sin CDN ni servicios externos.
- Consumo: costo conocido diario por proveedor, solicitudes API externas y llamadas locales, y
  tokens de entrada/salida por proveedor. Comparativo: latencia en segundos, resultados
  aprobado/fallido/bloqueado, costo conocido por escenario con cobertura y matriz de escenarios.
- Tooltips con unidad/cobertura, leyendas, exportación PNG, tablas accesibles y mensajes de datos
  ausentes. `usage-charts.js` reinicializa tras HTMX, libera instancias y respeta
  `prefers-reduced-motion`.
- Se mantiene la separación entre consumo completo (incluye bloqueados) y comparativo funcional
  sobre la muestra común de 9 escenarios; los totales conocidos siguen siendo parciales.
- Pruebas: `make check` con **717 passed**, 37 deselected; integraciones afectadas **8 passed**.
  Capturas y PNG exportado en `docs/evidencia/005-panel-uso-ia/`.

**Pendiente sin cambios**: T039, tiempos excedidos de Ollama, errores de salida estructurada externa
y el informe breve S10.

## Estabilización 005 (2026-11-23)

- **Tiempos de Ollama:** causa: timeout httpx por lectura, no plazo total; el plazo se comprobaba
  después de la llamada. Se añadió un transporte con deadline total y un mínimo de tiempo restante
  para iniciar otra operación. No se aumentaron 90 s/llamada ni 120 s/turno. Prueba local:
  `model_timeout` en 3 656 ms con timeout de 0,5 s. Persisten los límites y la variabilidad del
  modelo local; cerrar la espera HTTP no garantiza detener la inferencia en Ollama.
- **Salidas externas:** la evidencia histórica no conservó finish_reason ni contenido crudo; 13/19
  tokens de salida no sostienen truncamiento por el límite de 1200. Se mejoró el parser para extraer
  el primer objeto JSON completo, se añadió `extra="forbid"` y un motivo seguro
  (`empty_content`, `json_invalid`, `schema_mismatch`, `truncated_content`). La reproducción real
  externa sigue pendiente.
- **S10:** causa: el umbral global 0.5033 filtró los fragmentos de respaldo/acceso (0.399/0.326/
  0.251), dejando 0 hits. Se añadió recuperación de respaldo solo para preguntas de informe, sin
  cambiar el umbral global. Prompt `chat-v9` y persistencia de recomendaciones/limitaciones.
  Corrida local: 2 hits `expanded_case`, `answered`, 3 recomendaciones y limitación; 44 631 ms.
- **S07 externo:** una respuesta exclusivamente de herramienta (sin claims documentales) puede
  persistir sin citas. Si hay claims documentales rechazados, se conserva reparación/abstención;
  no se eliminan silenciosamente ni se presentan como verificados.
- **T039:** marker `external`, `make check` excluye externas y `pytest -m external` omite sin
  autorización explícita. La infraestructura está lista; la aceptación externa real no se declara.
- Pruebas: `make check` **734 passed**, 38 deselected; integraciones afectadas **8 passed**;
  externas **1 skipped**. Evidencia en `docs/evidencia/005-estabilizacion/`.
- Sin llamadas pagadas nuevas. No se inició Telegram ni 003.
