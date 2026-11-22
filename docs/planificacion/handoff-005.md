# Handoff — 005 Generador configurable (Entregas 1–2)

**Fecha**: 2026-11-22
**Estado**: Entregas 1–2 implementadas; 005 no aceptada; T035–T042 pendientes.
**Rama**: `005-generador-configurable`.

## 1. Estado actual

- **T001–T034 completadas.**
- Ollama real operativo; DeepSeek/Anthropic implementados y probados **solo con transporte simulado**.
- `make check`: **637 passed, 37 deselected**.
- Regresión real afectada: `test_ollama_provider_regression` + `test_answer_real` → **2 passed**
  (98.81 s).
- Migración probada sobre base temporal (`test_provider_run_record`: 2 passed).
- Sin llamadas externas reales, sin credenciales, sin presupuesto aprobado.

## 2. Qué está implementado

### Configuración efectiva

- `SECGUARD_GENERATION_PROVIDER/MODEL/MAX_OUTPUT/TOKENS/TIMEOUT/REASONING`.
- Precedencia entorno > `.env` > predeterminados; compatibilidad Ollama con nombres anteriores.
- Contador, presupuesto de salida, timeout y evidencia usan el perfil efectivo.
- Secretos `SecretStr`; `.env.example` sin claves.

### Adaptadores

- `DeepSeekGenerator`: JSON Output, `thinking=disabled`, uso/caché, errores normalizados.
- `AnthropicGenerator`: Structured Outputs, `count_tokens`, uso/caché, errores normalizados.
- `ProviderRegistry` selecciona una vez por turno; sin grafo duplicado ni fallback.

### Contexto, costo y presupuesto

- `EstimatedPromptCounter` (DeepSeek) y `AnthropicPromptCounter` (count_tokens o estimación).
- Tarifas `2026-11-22`; costo desconocido si falta uso/tarifa.
- `provider_budget_ledger`: reserva antes, liquidación/reconciliación después.
- Saldo global y por turno separados; cero bloquea antes de cualquier envío.
- `provider_usage` por llamada; `runs` agrega uso/costo.

### Autorización y privacidad

- `external_processing_authorizations` + `scripts/external_authorization.py`.
- Sin autorización no hay llamada ni conteo externo.
- `public_corpus` filtra evidencia del caso e historial.
- `findings_query` externo solo `fictional_case` + `origin=synthetic`; importados bloqueados.
- Redacción de secretos/rutas; LangSmith independiente.

## 3. Archivos clave

```text
src/secguard_advisor/conversation/providers/{base,registry,context,cost,usage,
  deepseek,anthropic,http_common,redaction}.py
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

## 4. Pruebas

| Área | Archivo |
|---|---|
| Configuración efectiva | `tests/unit/test_effective_generation_config.py` |
| Contexto | `tests/unit/test_provider_context.py` |
| Costo | `tests/unit/test_provider_cost.py` |
| Presupuesto | `tests/unit/test_budget_ledger.py` |
| Autorización | `tests/unit/test_external_authorization.py` |
| Herramientas externas | `tests/unit/test_external_tool_block.py` |
| Uso persistido | `tests/unit/test_provider_usage_persistence.py` |
| Redacción | `tests/unit/test_secret_redaction.py` |
| LangSmith | `tests/unit/test_langsmith_independence.py` |
| Contrato DeepSeek | `tests/contract/test_deepseek_adapter.py` |
| Contrato Anthropic | `tests/contract/test_anthropic_adapter.py` |
| Evidencia | `tests/contract/test_run_provider_view.py` |
| Compuerta | `tests/contract/test_external_authorization_gate.py` |

## 5. Límites y riesgos abiertos

- Ningún proveedor externo fue llamado realmente.
- Esquema, thinking, conteo y tarifas deben revalidarse contra las APIs reales.
- DeepSeek: caché omitida = 0; feriados chinos no modelados.
- Anthropic: `input_tokens` tratado como cache miss.
- La estimación DeepSeek no es exacta ni garantiza no truncamiento.
- La regresión real completa de 001/002 no se repitió; se ejecutaron las afectadas y `make check`.

## 6. Próximo paso

Antes de T035–T039:

1. Aprobar presupuesto global y por turno.
2. Configurar credenciales en `.env` local.
3. Autorizar un caso `fictional_case`/`public_corpus` con la CLI.
4. Revalidar modelos, precios y capacidades en documentación oficial.
5. Ejecutar la comparación fija de diez preguntas y guardar reportes.
6. No declarar aceptación de un proveedor externo sin resultados reales.
