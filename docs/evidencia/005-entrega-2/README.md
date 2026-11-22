# 005 — Evidencia de la Entrega 2 (T015–T034)

**Fecha**: 2026-11-22
**Rama**: `005-generador-configurable`
**Estado**: Entrega 2 implementada y probada contra transporte HTTP simulado. **005 no está aceptada.**
**Llamadas reales externas**: ninguna. No hay presupuesto aprobado ni credenciales.

## Alcance implementado

- Adaptadores **DeepSeek Flash** (`deepseek-flash`) y **Anthropic Claude Haiku 5.5**
  (`claude-haiku-5-5`) sobre el contrato común.
- Configuración efectiva unificada: transporte, contador, reserva de salida, timeouts y evidencia.
- Admisión de contexto por proveedor (GGUF solo Ollama; `count_tokens` en Anthropic; estimación
  conservadora identificada en DeepSeek).
- Tarifas fechadas, uso observado por llamada, costo calculado o `unknown`.
- Reserva y liquidación de presupuesto, con saldo global y saldo del turno.
- Autorización externa por caso y CLI local.
- Bloqueo de Qualys/importados y de `findings_query` externo fuera de `fictional_case` +
  `origin=synthetic`.
- Redacción centralizada de secretos/rutas y evidencia de uso/costo.

## Configuración (sin secretos)

```text
SECGUARD_GENERATION_PROVIDER=ollama|deepseek|anthropic
SECGUARD_GENERATION_MODEL=...
SECGUARD_GENERATION_MAX_OUTPUT_TOKENS=...
SECGUARD_GENERATION_TIMEOUT_SECONDS=...
SECGUARD_GENERATION_REASONING=off|low|high
DEEPSEEK_API_KEY=            # vacío por defecto
ANTHROPIC_API_KEY=           # vacío por defecto
DEEPSEEK_BASE_URL=https://api.deepseek.com
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_VERSION=2026-10-21
SECGUARD_EXTERNAL_BUDGET_USD=0
SECGUARD_EXTERNAL_RUN_BUDGET_USD=0
SECGUARD_EXTERNAL_TARIFF_VERSION=2026-11-22
SECGUARD_EXTERNAL_CONTEXT_WINDOW_TOKENS=128000
SECGUARD_EXTERNAL_ESTIMATE_CHARS_PER_TOKEN=2.0
SECGUARD_EXTERNAL_ESTIMATE_OVERHEAD_TOKENS=64
```

Ningún valor real de clave se versiona, imprime ni escribe en SQLite.

## Autorización local

```bash
uv run python scripts/external_authorization.py --case <case_id> \
  --scope fictional_case --authorized-by "Revisora local" --note "Prueba ficticia"
uv run python scripts/external_authorization.py --list --case <case_id>
uv run python scripts/external_authorization.py --case <case_id> --revoke
```

La credencial sola no autoriza. Sin autorización vigente no se llama al proveedor ni al contador
externo.

## Comandos y resultados observados

```text
make check
  → 637 passed, 37 deselected, 17 warnings

uv run pytest tests/integration/test_ollama_provider_regression.py \
                 tests/integration/test_answer_real.py -q
  → 2 passed in 98.81 s (Ollama real)

uv run pytest tests/unit/test_provider_run_record.py -q
  → 2 passed (migración y registro)
```

Pruebas nuevas principales:

| Área | Archivo | Resultado |
|---|---|---|
| Configuración efectiva | `tests/unit/test_effective_generation_config.py` | 3 passed |
| Contexto por proveedor | `tests/unit/test_provider_context.py` | 4 passed |
| Costos | `tests/unit/test_provider_cost.py` | 8 passed |
| Presupuesto | `tests/unit/test_budget_ledger.py` | 7 passed |
| Autorización | `tests/unit/test_external_authorization.py` | 4 passed |
| Herramientas externas | `tests/unit/test_external_tool_block.py` | 6 passed |
| Uso persistido | `tests/unit/test_provider_usage_persistence.py` | 3 passed |
| Redacción | `tests/unit/test_secret_redaction.py` | 3 passed |
| LangSmith independiente | `tests/unit/test_langsmith_independence.py` | 2 passed |
| Contrato DeepSeek | `tests/contract/test_deepseek_adapter.py` | 6 passed |
| Contrato Anthropic | `tests/contract/test_anthropic_adapter.py` | 4 passed |
| Evidencia de uso | `tests/contract/test_run_provider_view.py` | 2 passed |
| Compuerta de autorización | `tests/contract/test_external_authorization_gate.py` | 2 passed |

## Qué demuestran las pruebas simuladas

- DeepSeek usa `response_format=json_object`, `max_tokens`, `thinking=disabled` y JSON validado.
- Anthropic usa `output_config.format` JSON Schema, `max_tokens`, sin `temperature`, y JSON validado.
- Un contenido vacío o no JSON produce `invalid_model_output`.
- 401/403 → `provider_auth_error`; 429 → `provider_rate_limited`; timeout → `model_timeout`.
- Los errores no incluyen la clave ni el cuerpo del proveedor.
- Sin autorización o con presupuesto cero, no se llama al generador ni al contador externo.
- `public_corpus` no envía evidencia del caso ni historial previo.
- `findings_query` externo solo se permite en `fictional_case` con `origin=synthetic`.
- El uso desconocido conserva la reserva y produce costo `unknown`, nunca cero.
- La reserva se reconcilia al reiniciar si la ejecución ya terminó.

## Limitaciones

- **Ningún proveedor externo fue llamado realmente.** Los contratos usan `httpx.MockTransport`.
- No se validó contra las APIs reales el esquema JSON, el modo de razonamiento, el conteo de tokens
  ni las tarifas. Debe hacerse en la comparación real posterior, con presupuesto.
- DeepSeek: si la respuesta omite campos de caché, se asume 0 (conservador); no se modelan feriados
  chinos en peak/off-peak.
- Anthropic: los tokens de entrada se tratan como cache miss; los tokens de caché se suman con su
  tarifa. La semántica exacta debe confirmarse contra la API real.
- La estimación de DeepSeek no es un conteo exacto ni una garantía contra truncamiento.
- La regresión real completa de 001/002 no se repitió en esta entrega; se ejecutaron las pruebas
  reales afectadas (`test_answer_real`, `test_ollama_provider_regression`) y `make check`.
- `LANGSMITH_TRACING=false`; no se enviaron trazas.
- No se modificaron `storage/`, `storage/demo`, Chroma, Qdrant ni datos existentes.

## Pasos para la comparación real posterior

1. Aprobar presupuesto global y por turno; definir montos sin inventarlos.
2. Configurar credenciales solo en `.env` local.
3. Autorizar un caso `fictional_case` o `public_corpus` con la CLI.
4. Revalidar identificadores, precios y capacidades en documentación oficial.
5. Ejecutar el conjunto fijo de diez preguntas con cada proveedor y guardar reportes.
6. Comparar latencia, citas, estructura, seguimiento de instrucciones, recomendaciones y costo.
7. Si se detecta una diferencia, corregir y repetir solo lo afectado.

## Commits

- `7d4f374` — adaptadores externos, contexto, costo, presupuesto, autorización, privacidad y
  evidencia de uso.
- Commit documental de esta evidencia: ver `git log -- docs/evidencia/005-entrega-2`.
