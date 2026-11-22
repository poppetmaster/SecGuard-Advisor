# 005 — Último resultado (Entregas 1–2 implementadas)

**Fecha**: 2026-11-22 (America/Bogota, `-05`)
**Rama**: `005-generador-configurable`
**Estado**: **T001–T034 implementadas y verificadas con Ollama real y transporte externo simulado.
005 no está aceptada.**
**Alcance**: configuración y contrato común, adaptadores DeepSeek/Anthropic, contexto, costo,
presupuesto, autorización, privacidad y evidencia. La comparación real y la aceptación (T035–T042)
siguen pendientes.

## Dictamen

La Entrega 2 está completa dentro del alcance permitido: los adaptadores externos existen, usan el
contrato común y están cubiertos por pruebas de contrato con `httpx.MockTransport`. No se realizaron
llamadas reales a DeepSeek ni Anthropic, no se solicitó presupuesto ni credenciales y no se declara
ningún proveedor externo aceptado en uso real.

Ollama sigue operativo y su regresión real pasó. `make check` quedó en verde.

## Estado por tarea

| Rango | Estado | Evidencia |
|---|---|---|
| T001–T014 Entrega 1 | Completadas | Configuración, registro, Ollama, esquema tipado, migración y evidencia. |
| T015–T018 adaptadores | Completadas | Contratos simulados DeepSeek/Anthropic; adaptadores `httpx`. |
| T019–T020 contexto | Completadas | GGUF solo Ollama; `count_tokens` Anthropic; estimación DeepSeek identificada. |
| T021–T022 costo | Completadas | Tarifas fechadas, cache/peak, `unknown`, nunca cero. |
| T023–T024 presupuesto | Completadas | Reserva, liquidación, reconciliación, saldo global y por turno. |
| T025–T026 autorización | Completadas | Tabla por caso, servicio y CLI local. |
| T027–T028 herramientas externas | Completadas | Solo `fictional_case` + `origin=synthetic`; importados bloqueados. |
| T029–T030 redacción | Completadas | Secretos/rutas en errores, trazas y evidencia. |
| T031–T032 evidencia de uso | Completadas | Uso por llamada, costo y página de ejecución. |
| T033 LangSmith independiente | Completada | Activar externo no habilita trazas. |
| T034 documentación | Completada | Este documento, handoff y `docs/evidencia/005-entrega-2/`. |
| T035–T042 comparación/aceptación | Pendientes | No iniciadas. |

## Corrección de configuración efectiva

Se unificaron los consumidores para que todos usen el perfil seleccionado:

- `web/app.py` construye el contador con `build_prompt_counter(settings)`:
  - Ollama: `LazyPromptCounter(settings.provider_model)` (modelo efectivo, no el antiguo fijo).
  - DeepSeek: estimador conservador identificado.
  - Anthropic: `count_tokens` (o estimación si falla).
- `conversation/budget.py` calcula el límite y la reserva con `provider_context_window` y
  `provider_max_output_tokens`.
- `conversation/nodes.py` usa `provider_timeout_seconds`; se eliminó `generation_config` con
  parámetros anteriores.
- `Run` registra `generator_max_output_tokens` y `generator_timeout_seconds`; la evidencia los muestra.
- Las pruebas usan valores nuevos distintos de los antiguos (modelo, 64 tokens, 12.5 s).

## Adaptadores externos

### DeepSeek

- Endpoint `/chat/completions`, modelo `deepseek-flash`.
- `response_format={"type":"json_object"}`, esquema en el system prompt, `max_tokens`.
- `thinking=disabled` por defecto; sin reintentos implícitos del transporte.
- Errores normalizados sin cuerpo del proveedor.
- Uso: `prompt_tokens`, `completion_tokens`, `prompt_cache_hit_tokens`.

### Anthropic

- Endpoint `/v1/messages`, modelo `claude-haiku-5-5`, `output_config.format` JSON Schema.
- `max_tokens`; sin `temperature`/`top_p`/`top_k`; thinking adaptativo del proveedor.
- Errores normalizados; `count_tokens` para admisión.
- Uso: `input_tokens`, `output_tokens`, `cache_read_input_tokens`,
  `cache_creation_input_tokens`.

Ninguno duplica el grafo ni tiene fallback.

## Presupuesto, uso y costo

- `provider_budget_ledger` reserva antes de la llamada y liquida o reconcilia después.
- Saldo global (`external_budget_usd`) y saldo del turno (`external_run_budget_usd`) son límites
  distintos; el turno no reinicia el global.
- Una llamada enviada o de envío incierto sin uso confirmado conserva la reserva; no se libera como
  gasto cero.
- `provider_usage` registra decisión, generación, reparación y errores.
- Costo calculado con tarifa `2026-11-22`; si falta uso o tarifa, `unknown`.
- `external_budget_usd=0` bloquea antes de cualquier envío, incluido el conteo externo.

## Autorización y privacidad

- `external_processing_authorizations`: alcance `public_corpus` o `fictional_case`, política,
  identidad declarada, fecha y revocación.
- CLI: `uv run python scripts/external_authorization.py` para otorgar, listar y revocar.
- Sin autorización vigente no se llama al proveedor ni al contador externo.
- `public_corpus` no envía evidencia del caso ni historial previo.
- `findings_query` externo solo en `fictional_case` + `origin=synthetic`; importados/Qualys se
  bloquean.
- LangSmith sigue independiente y desactivado por defecto.
- Redacción centralizada de secretos, rutas y cabeceras.

## Comandos y resultados observados

```text
make check
  → 637 passed, 37 deselected, 17 warnings (17.80 s)

uv run pytest tests/integration/test_ollama_provider_regression.py \
                 tests/integration/test_answer_real.py -q
  → 2 passed in 98.81 s (Ollama real)

uv run pytest tests/unit/test_provider_run_record.py -q
  → 2 passed (migración sobre base temporal)
```

Las pruebas externas son simuladas: no hay llamadas reales ni evidencia de aceptación de DeepSeek o
Anthropic.

## Archivos principales

```text
src/secguard_advisor/conversation/providers/{base,registry,context,cost,usage}.py
src/secguard_advisor/conversation/providers/{deepseek,anthropic,http_common,redaction}.py
src/secguard_advisor/cases/external.py
src/secguard_advisor/evidence/budget.py
src/secguard_advisor/config.py
src/secguard_advisor/conversation/{budget,nodes,turn,context,views}.py
src/secguard_advisor/db/models.py
src/secguard_advisor/web/{app,errors}.py
src/secguard_advisor/web/routes/chat.py
src/secguard_advisor/web/templates/runs/show.html
alembic/versions/e6f7a8b9c0d1_add_provider_usage_budget_auth.py
scripts/external_authorization.py
```

## Limitaciones

- Sin llamadas reales a proveedores externos; los contratos usan transporte simulado.
- Esquema JSON, thinking, conteo y tarifas deben revalidarse contra las APIs reales.
- DeepSeek: caché omitida se asume 0; feriados chinos no modelados.
- Anthropic: tokens de entrada tratados como cache miss; confirmar semántica real.
- La estimación DeepSeek no es un conteo exacto ni garantía contra truncamiento.
- La regresión real completa de 001/002 no se repitió; se ejecutaron las pruebas reales afectadas y
  `make check`.
- No se modificaron `storage/`, `storage/demo`, Chroma, Qdrant ni datos existentes.
- `LANGSMITH_TRACING=false`.

## Próximos pasos

1. Aprobar presupuesto global y por turno.
2. Configurar credenciales locales sin versionarlas.
3. Revalidar identificadores, precios y capacidades.
4. Ejecutar la comparación real (T035–T039) con el conjunto fijo de diez preguntas.
5. Regresión final y aceptación (T040–T042) solo con evidencia.

## Commits

- `1d5f856`, `db17347`, `bdcd892` — Entrega 1.
- `7d4f374` — Entrega 2: adaptadores, contexto, costo, presupuesto, autorización y privacidad.
- Commit documental de este informe: ver `git log -- docs/planificacion/005-ultimo-resultado.md`.
