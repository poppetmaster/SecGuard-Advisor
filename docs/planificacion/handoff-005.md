# Handoff — 005 Generador configurable (Entrega 1)

**Fecha**: 2026-11-22
**Estado**: Entrega 1 implementada; 005 no aceptada.
**Rama**: `005-generador-configurable`.

## 1. Estado actual

- **T001–T014 completadas.** Configuración, protocolo/registro, Ollama operativo, esquema tipado,
  migración y evidencia.
- **T015–T042 pendientes.** DeepSeek/Anthropic, autorización externa, presupuesto, comparación y
  aceptación.
- `make check`: **585 passed, 37 deselected**.
- Regresión real: `tests/acceptance/test_journey_real.py` **1 passed** (715 s), con cita, memoria y
  herramienta.
- Regresión del registro: `tests/integration/test_ollama_provider_regression.py` **1 passed**.
- Migración: `tests/unit/test_provider_run_record.py` **2 passed** (datos anteriores conservados).
- No se ejecutaron llamadas pagadas ni se solicitaron claves.

## 2. Qué se implementó

### Configuración

- `SECGUARD_GENERATION_PROVIDER` (`ollama|deepseek|anthropic`), modelo, límite de salida, timeout y
  razonamiento.
- Precedencia entorno > `.env` > predeterminados.
- Compatibilidad Ollama: `SECGUARD_GENERATION_MODEL` > `OLLAMA_MODEL`;
  `SECGUARD_GENERATION_MAX_OUTPUT_TOKENS` > `generator_num_predict`;
  `SECGUARD_GENERATION_TIMEOUT_SECONDS` > `llm_timeout_seconds`.
- Credenciales `SecretStr`, plantilla sin claves, validación de arranque.
- Presupuesto global y por turno declarados; `0` bloquea externos (implementación en Entrega 2).

### Contrato y registro

- `GeneratorProtocol` y `ProviderRegistry`.
- `OllamaGenerator` adaptado al protocolo (`provider`, `identity`, `close`).
- `create_app` usa el registro; `start_question_turn` registra proveedor/identidad.
- Proveedores externos no implementados: HTTP 501 `provider_not_implemented`, sin fallback.

### Herramientas

- `ToolDecision.arguments` = `ToolArguments` (claves estrictas, sin `case_id` ni extras).
- Valores validados por `FindingsArguments`/`parse_arguments`; se conserva la corrección.
- Se persisten solo los argumentos proporcionados.

### Persistencia y evidencia

- Migración `d4b8c1e2f3a5`: `generator_provider`, `generator_identity`, `cost_status`, `cost_usd`,
  `cost_tariff_version`.
- Filas anteriores: `ollama`, `not_applicable`.
- La página de ejecución muestra proveedor, modelo, identidad, digest y costo de API.
- Ollama: «No aplicable (API)», sin afirmar costo operativo total cero.

## 3. Archivos clave

```text
src/secguard_advisor/conversation/providers/{base,registry}.py
src/secguard_advisor/config.py
src/secguard_advisor/conversation/llm.py
src/secguard_advisor/conversation/nodes.py
src/secguard_advisor/conversation/prompts.py
src/secguard_advisor/conversation/turn.py
src/secguard_advisor/db/models.py
src/secguard_advisor/evidence/runs.py
src/secguard_advisor/web/{app,errors}.py
src/secguard_advisor/web/routes/chat.py
src/secguard_advisor/web/templates/runs/show.html
alembic/versions/d4b8c1e2f3a5_add_generation_provider.py
tests/unit/test_provider_config.py
tests/unit/test_provider_registry.py
tests/unit/test_tool_decision_schema.py
tests/unit/test_provider_run_record.py
tests/contract/test_run_provider_view.py
tests/contract/test_provider_not_implemented.py
tests/integration/test_ollama_provider_regression.py
tests/acceptance/test_journey_real.py
```

## 4. Decisiones y límites

- El esquema de argumentos es estructural: rechaza `case_id`/extras, pero delega los valores a la
  validación existente para conservar la corrección de argumentos inválidos.
- El prompt de decisión (`decide-v5`) incluye ejemplos y la instrucción de no repetir una consulta ya
  respondida. La prueba real exige una llamada filtrada correcta, no que sea la primera.
- El presupuesto no se implementó en la Entrega 1; solo se declaró la configuración.
- La autorización externa no se implementó; los externos no llegan a llamarse.
- La regresión real usa el presupuesto de prueba preexistente (600 s/300 s); el producto conserva
  120 s/90 s.
- No se modificaron `storage/`, `storage/demo`, Chroma, Qdrant ni datos existentes.

## 5. Próximo paso

Entrega 2 (T015–T034):

1. Adaptadores DeepSeek y Anthropic contra servidor simulado.
2. Admisión de contexto por proveedor.
3. Costo, reserva/liquidación y reconciliación.
4. Autorización externa por caso, redacción y bloqueo de herramientas importadas.
5. Evidencia de uso/costo.

Antes de ejecutar pruebas reales externas: presupuesto aprobado, credenciales y alcance
`public_corpus`/`fictional_case` confirmados. No se inicia 005 Entrega 2 en este cierre.

## 6. Riesgos abiertos

| Riesgo | Mitigación |
|---|---|
| Fuga de contenido privado | Autorización por caso + minimización (Entrega 2) |
| Costo real mayor que la reserva | Reserva conservadora y conciliación (Entrega 2) |
| JSON inválido/vacío del proveedor | Reparación acotada y validación local |
| Contexto mal medido | Medición por proveedor y margen |
| Secreto en error | Redacción centralizada y pruebas de escaneo |
| Variación del modelo local | Prompt con ejemplos y pruebas deterministas para filtros |
