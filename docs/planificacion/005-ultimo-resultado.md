# 005 — Último resultado (Entrega 1 implementada)

**Fecha**: 2026-11-22 (America/Bogota, `-05`)
**Rama**: `005-generador-configurable`
**Estado**: **Entrega 1 (T001–T014) implementada y verificada. 005 no está aceptada.**
**Alcance**: configuración y contrato común de proveedores, conservando Ollama como generador
operativo. DeepSeek y Anthropic siguen sin implementar.

## Dictamen

La Entrega 1 está completa: la aplicación selecciona el proveedor de forma explícita, valida la
configuración, conserva Ollama con su comportamiento actual, registra proveedor/modelo/identidad/
límites y costo de API no aplicable, y rechaza proveedores externos no implementados sin fallback.
La migración es aditiva y conserva las ejecuciones anteriores. `make check` y la regresión real con
Ollama/Qdrant pasan.

Lo que **no** está hecho: adaptadores DeepSeek/Anthropic, autorización externa, presupuesto,
comparación y aceptación de 005. No se ejecutaron llamadas pagadas ni se solicitaron claves.

## Estado por tarea

| Tarea | Estado | Evidencia |
|---|---|---|
| T001 pruebas de configuración | Completada | `tests/unit/test_provider_config.py`: 10 passed. |
| T002 Settings de proveedor | Completada | `config.py`: proveedor, modelo, límites, secretos, presupuesto. |
| T003 `.env.example` | Completada | Plantilla sin claves; `.env` ignorado por Git. |
| T004 pruebas de registro | Completada | `tests/unit/test_provider_registry.py`: 4 passed. |
| T005 protocolo y registro | Completada | `conversation/providers/{base,registry}.py`. |
| T006 pruebas del esquema tipado | Completada | `tests/unit/test_tool_decision_schema.py`: 5 passed. |
| T007 `ToolDecision.arguments` tipado | Completada | `ToolArguments` con claves estrictas; valores delegados a `FindingsArguments`. |
| T008 pruebas de migración/registro | Completada | `tests/unit/test_provider_run_record.py`: 2 passed. |
| T009 migración y registro por ejecución | Completada | `alembic/versions/d4b8c1e2f3a5_*.py`; `create_run`/`turn.py`. |
| T010 contrato de evidencias | Completada | `tests/contract/test_run_provider_view.py`: 1 passed. |
| T011 vista de proveedor/costo | Completada | `runs/show.html` y `conversation/views.py`. |
| T012 regresión real Ollama/Qdrant | Completada | `test_journey_real.py`: 1 passed; `test_ollama_provider_regression.py`: 1 passed. |
| T013 ausencia de fallback | Completada | `tests/contract/test_provider_not_implemented.py`: 1 passed. |
| T014 documentación de la entrega | Completada | Este documento, handoff y `docs/evidencia/005-entrega-1/`. |
| T015–T042 | Pendientes | Entrega 2 y 3; no iniciadas. |

## Decisiones implementadas

### Configuración y precedencia

- `SECGUARD_GENERATION_PROVIDER` (`ollama` predeterminado, `deepseek`, `anthropic`).
- Para Ollama, los nombres nuevos tienen precedencia sobre los anteriores:
  - `SECGUARD_GENERATION_MODEL` > `OLLAMA_MODEL`.
  - `SECGUARD_GENERATION_MAX_OUTPUT_TOKENS` > `generator_num_predict`.
  - `SECGUARD_GENERATION_TIMEOUT_SECONDS` > `llm_timeout_seconds`.
- Precedencia general: variables de entorno > `.env` > predeterminados.
- Credenciales `SecretStr` (`DEEPSEEK_API_KEY`, `ANTHROPIC_API_KEY`); ausentes por defecto.
- Un proveedor externo sin credencial no arranca. Un proveedor desconocido o un límite inválido
  tampoco.
- `external_budget_usd` y `external_run_budget_usd` existen; `0` bloquea externos en la Entrega 2.

### Contrato y registro

- `GeneratorProtocol` con `provider`, `model`, `identity`, `decide`, `generate`, `last_usage`,
  `close`.
- `ProviderRegistry` resuelve el generador una vez por turno desde `Settings`.
- `OllamaGenerator` implementa el protocolo y conserva su comportamiento.
- Un proveedor externo configurado lanza `ProviderNotImplemented` (código
  `provider_not_implemented`, HTTP 501) y **no** cae a Ollama.
- La fábrica `create_app` usa el registro; el turno registra el proveedor y la identidad.

### Argumentos de herramienta

- `ToolDecision.arguments` usa `ToolArguments`, un esquema estructural con `extra="forbid"` que
  rechaza `case_id` y claves desconocidas.
- Los valores (severidad, estado, límites) se validan con `FindingsArguments`/`parse_arguments`, por
  lo que se conserva la corrección de argumentos inválidos por el modelo.
- Los consumidores guardan solo los argumentos proporcionados (`exclude_unset=True`), sin cambiar
  conteos, filtros ni aislamiento.

### Persistencia y evidencia

- Columnas nuevas en `runs`: `generator_provider`, `generator_identity`, `cost_status`, `cost_usd`,
  `cost_tariff_version`.
- Las filas anteriores se rellenan con `provider=ollama`, `cost_status=not_applicable`.
- La página de ejecución muestra proveedor, generador, identidad, digest y costo de API.
- Para Ollama: **No aplicable (API)**. No se afirma costo operativo total cero.
- No se guardan secretos.

## Comandos y resultados observados

```text
make check
  → 585 passed, 37 deselected, 17 warnings

uv run pytest tests/acceptance/test_journey_real.py -q
  → 1 passed in 715.47 s (11:55), Ollama + Qdrant reales
     cubre consulta con cita, memoria y herramienta

uv run pytest tests/integration/test_ollama_provider_regression.py -q
  → 1 passed in 7.68 s

uv run pytest tests/unit/test_provider_run_record.py -q
  → 2 passed (migración desde b7f2c9d1e4a6 con datos anteriores + registro)
```

Pruebas enfocadas adicionales: configuración (10), registro (4), esquema (5), contrato de evidencia
(1) y ausencia de fallback (1). Todas en verde.

## Limitaciones observadas

- DeepSeek y Anthropic no están implementados; el error es explícito y no hay fallback.
- No se ejecutaron llamadas externas ni se solicitaron credenciales.
- La regresión real usa el presupuesto de prueba ya existente de 600 s/300 s para el modelo local;
  el producto conserva 120 s/90 s. No se amplió durante esta entrega para ocultar fallos.
- El modelo local puede variar en la decisión de herramienta. Se mejoró el prompt de decisión con
  ejemplos y la instrucción de no repetir una consulta ya respondida; la prueba real exige que
  exista una llamada filtrada correcta, no que sea la primera.
- Los proveedores externos no tienen aún autorización por caso, presupuesto ni comparación.

## Archivos modificados

```text
src/secguard_advisor/config.py
src/secguard_advisor/conversation/llm.py
src/secguard_advisor/conversation/nodes.py
src/secguard_advisor/conversation/prompts.py
src/secguard_advisor/conversation/turn.py
src/secguard_advisor/conversation/views.py
src/secguard_advisor/conversation/providers/{__init__,base,registry}.py
src/secguard_advisor/db/models.py
src/secguard_advisor/evidence/runs.py
src/secguard_advisor/web/app.py
src/secguard_advisor/web/errors.py
src/secguard_advisor/web/routes/chat.py
src/secguard_advisor/web/templates/runs/show.html
alembic/versions/d4b8c1e2f3a5_add_generation_provider.py
.env.example
tests/unit/test_provider_config.py
tests/unit/test_provider_registry.py
tests/unit/test_tool_decision_schema.py
tests/unit/test_provider_run_record.py
tests/contract/test_run_provider_view.py
tests/contract/test_provider_not_implemented.py
tests/integration/test_ollama_provider_regression.py
tests/acceptance/test_journey_real.py
```

## Evidencia persistente

- `docs/evidencia/005-entrega-1/README.md`
- `docs/planificacion/handoff-005.md`
- `specs/005-generador-configurable/tasks.md` (T001–T014 marcadas)

## Próximo paso

Revisar la Entrega 1. Si se aprueba, iniciar la **Entrega 2 (T015–T034)**: adaptadores DeepSeek y
Anthropic contra servidor simulado, contexto, costo, presupuesto, autorización externa y bloqueo de
herramientas importadas. No se inicia 005 Entrega 2 en este cierre.
