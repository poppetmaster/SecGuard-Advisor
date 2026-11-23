# 005 — Evidencia de la Entrega 3 (T035–T042)

**Fecha**: 2026-11-22
**Rama**: `005-generador-configurable`
**Estado**: R1–R3 corregidos; comparación local real y externa simulada; **005 con aceptación local
parcial, sin aceptación de proveedores externos**.

## R1 — Reintento externo con autorización y alcance

**Corrección**
- `start_retry_turn` usa la misma ruta que el inicio: `resolve_turn_profile`,
  `create_turn_record` y `build_turn_context`.
- `create_turn_record` comprueba `ensure_external_allowed` antes de crear la ejecución.
- Una autorización ausente o revocada bloquea el reintento.
- `external_scope` y `external_authorization_id` se propagan al contexto y a `runs`.
- `public_corpus` limpia contexto del caso e historial y filtra evidencias privadas.
- `findings_query` externo con datos importados sigue bloqueado.
- El intento nuevo registra proveedor, modelo, identidad y parámetros efectivos; reutiliza la
  pregunta original y conserva `attempt_no`/`retry_of_run_id`.

**Pruebas**: `tests/unit/test_retry_external_scope.py` — **6 passed**:
- reintento sin autorización con generador/contador “explosivos” → cero llamadas;
- `public_corpus` con señuelos privados en contexto, historial y fuentes;
- perfil efectivo y vista de ejecución;
- cambio local → externo;
- importados bloqueados en reintento.

## R2 — Timeout efectivo en adaptadores

**Corrección**
- `post_json` acepta `timeout_seconds` y lo pasa a `client.post(..., timeout=...)`.
- DeepSeek y Anthropic propagan el argumento por llamada.
- El nodo sigue acotando por `provider_timeout_seconds` y tiempo restante del turno.
- Sin reintentos implícitos; un timeout conserva la reserva comprometida.

**Pruebas**:
- `tests/contract/test_deepseek_adapter.py::test_per_call_timeout_reaches_the_transport`
- `tests/contract/test_anthropic_adapter.py::test_per_call_timeout_reaches_the_transport`

Con cliente de 12,5 s y llamada de 0,25 s, el transporte recibe `read=0.25`.

## R3 — Evidencia de configuración efectiva

**Corrección**
- Inicio y reintento persisten `generator_max_output_tokens`, `generator_timeout_seconds`,
  `external_authorization_id`, proveedor, modelo e identidad desde `TurnProfile`.
- Las ejecuciones históricas no se reescriben.

**Pruebas**: `test_retry_external_scope.py` (inicio, reintento, vista) con salida **64** y timeout
**12.5 s**; SQLite y la página muestran esos valores. El intento local anterior conserva 1200/90.

## T035–T038 — Comparación

- Conjunto congelado: `tests/fixtures/provider_comparison.py`, 10 preguntas (8 con cita esperada,
  2 de abstención), hash **`92778d5cdffca49c065354a4c5e816d8af678c30ae795d5fd506ffe8db5c5129`**.
- Ejecutor: `scripts/compare_providers.py` (JSON y Markdown).
- Pruebas: `tests/unit/test_provider_comparison.py` — **4 passed**.

### Ollama real

Reporte: `docs/evidencia/005-comparacion/ollama.json` y `ollama.md`.

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

Duración por pregunta: 6929, 7738, 6816, 8008, 8114, 9666, 10216, 16992, 25881 y 39123 ms.
Recomendaciones declaradas: 1. `missing_info` declarados: 2.
Cada turno registra `decide` y `agent` por separado en el JSON.

### DeepSeek/Anthropic simulados

- `deepseek-mock.json` / `deepseek-mock.md`: transporte `mock`, 10 turnos, costo calculado
  `0.000810 USD` (simulado), 0 respuestas con cita (el mock no produce claims).
- `anthropic-mock.json` / `anthropic-mock.md`: transporte `mock`, 10 turnos, costo calculado
  `0.000600 USD` (simulado), 0 respuestas con cita.

Estos reportes prueban el pipeline y el cálculo de costo con `httpx.MockTransport`. **No son
mediciones reales** y no se usan para aceptar proveedores.

### T039 — Comparación externa real

Pendiente. Reportes de omisión:
- `deepseek-real-pending.json`: «Sin presupuesto externo aprobado (external_budget_usd=0).»
- `anthropic-real-pending.json`: mismo motivo.

No se usó ninguna clave ni se realizó una llamada paga. La instrucción de esta ejecución no aporta un
monto autorizado.

## T040 — Regresión

```text
make check
  → 649 passed, 37 deselected, 17 warnings

make test-integration
  → 37 passed, 649 deselected, 14 warnings (1213.60 s = 20:13)
```

La regresión incluye 001/002/004 y la integración real de Ollama. La primera ejecución falló en
`test_qualys_import_real` porque el prompt de decisión no repetía una consulta con filtro distinto;
se corrigió (`decide-v6`) y la prueba pasó. No se relajaron criterios.

## T041 — Documentación

Actualizados `README.md`, `AGENTS.md`, la constitución, `tasks.md`, `005-ultimo-resultado.md` y
`handoff-005.md`.

## T042 — Aceptación

**Aceptación local parcial**: Ollama real, comparación local, correcciones R1–R3, `make check` y
`make test-integration` verdes. **Los proveedores externos no están aceptados**: solo hay contratos
simulados y no hay medición real ni presupuesto. T039 real permanece pendiente. T042 queda completada
como registro de aceptación parcial, no como aceptación integral de 005. La página
`/settings/ai` y su evidencia se documentan en `docs/evidencia/005-configuracion-ui/`.

## Limitaciones

- Evaluación semántica no realizada; solo comprobaciones automáticas.
- Corpus de comparación ficticio; no representa datos del usuario.
- Ollama tiene costo de API no aplicable; no se declara costo operativo total cero.
- Los reportes mock no acreditan calidad ni latencia real de DeepSeek/Anthropic.
- No se enviaron Qualys, derivados ni datos privados a APIs.
- No se modificaron `storage/`, `storage/demo`, Chroma ni Qdrant.

## Archivos cambiados principales

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

Ver `git log --oneline` en la rama `005-generador-configurable`.
