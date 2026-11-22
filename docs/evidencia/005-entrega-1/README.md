# 005 — Evidencia de la Entrega 1 (T001–T014)

**Fecha**: 2026-11-22
**Rama**: `005-generador-configurable`
**Estado**: Entrega 1 implementada y verificada. **005 no está aceptada.**

## Alcance

Configuración y contrato común de proveedores, conservando Ollama como generador operativo.
DeepSeek y Anthropic no se implementan en esta entrega. No se realizaron llamadas pagadas ni se
solicitaron credenciales.

## Resultados observados

```text
make check
  → 585 passed, 37 deselected, 17 warnings

uv run pytest tests/acceptance/test_journey_real.py -q
  → 1 passed in 715.47 s (11:55)
     Ollama + Qdrant reales; consulta con cita, memoria y herramienta

uv run pytest tests/integration/test_ollama_provider_regression.py -q
  → 1 passed in 7.68 s

uv run pytest tests/unit/test_provider_run_record.py -q
  → 2 passed
```

Pruebas enfocadas:

| Archivo | Resultado |
|---|---|
| `tests/unit/test_provider_config.py` | 10 passed |
| `tests/unit/test_provider_registry.py` | 4 passed |
| `tests/unit/test_tool_decision_schema.py` | 5 passed |
| `tests/unit/test_provider_run_record.py` | 2 passed |
| `tests/contract/test_run_provider_view.py` | 1 passed |
| `tests/contract/test_provider_not_implemented.py` | 1 passed |
| `tests/integration/test_ollama_provider_regression.py` | 1 passed |
| `tests/acceptance/test_journey_real.py` | 1 passed |

## Qué se verificó

### Configuración

- `SECGUARD_GENERATION_PROVIDER` predeterminado `ollama`.
- Precedencia entorno > `.env` > predeterminados.
- Compatibilidad: `SECGUARD_GENERATION_MODEL` > `OLLAMA_MODEL`; límite/timeout nuevos > antiguos.
- Credencial ausente para externo → fallo de arranque con el nombre de la variable.
- Proveedor desconocido, límite 0/negativo y timeout 0/negativo → rechazo.
- Secretos `SecretStr`; no aparecen en `repr`.

### Registro y fallback

- `ProviderRegistry` crea `OllamaGenerator` con el modelo/límites efectivos.
- Proveedor externo no implementado → `ProviderNotImplemented` (HTTP 501,
  `provider_not_implemented`), sin segunda llamada a Ollama.
- El mensaje nombra el proveedor y el modelo, no la credencial.

### Argumentos de herramienta

- `ToolArguments` rechaza `case_id` y campos extra.
- Los valores inválidos (severidad, límite) llegan a `FindingsArguments` y producen
  `invalid_arguments`, conservando la corrección existente.
- `model_dump(exclude_unset=True)` persiste solo los argumentos proporcionados.
- Los conteos, filtros y aislamiento de `findings_query` no cambian.

### Migración y evidencia

- Migración `d4b8c1e2f3a5` desde `b7f2c9d1e4a6` sobre base temporal con una ejecución anterior.
- La fila anterior queda `generator_provider=ollama`, `generator_identity=NULL`,
  `cost_status=not_applicable`, `cost_usd=NULL`.
- `start_question_turn` registra proveedor e identidad del generador.
- La página de ejecución muestra proveedor, modelo, identidad, digest y costo de API.
- Ollama: «No aplicable (API)»; el texto aclara que no mide el costo operativo local.

## Regresión real

`test_journey_real.py` se actualizó para construir el generador a través de `ProviderRegistry`.
Cubre:

- consulta documental con cita;
- memoria entre turnos;
- `findings_query` con datos sintéticos;
- abstención fuera de alcance;
- reintento controlado.

El modelo local puede variar en la decisión de herramienta. Se mejoró `DECISION_SYSTEM_PROMPT`
(`decide-v5`) con ejemplos y la instrucción de no repetir una consulta ya respondida. La prueba
exige que exista una llamada filtrada correcta, no que sea la primera.

## Limitaciones

- DeepSeek y Anthropic no implementados.
- Sin autorización externa, presupuesto, comparación ni aceptación de 005.
- La regresión real usa el presupuesto de prueba preexistente (600 s/300 s); el producto conserva
  120 s/90 s.
- No se modificaron `storage/`, `storage/demo`, Chroma, Qdrant ni datos existentes.
- `LANGSMITH_TRACING=false`; no se enviaron trazas.

## Commits

- `1d5f856` — configuración, registro, contrato y esquema tipado.
- `db17347` — persistencia, migración y evidencia de proveedor.
- Commit documental de esta evidencia: ver `git log -- docs/evidencia/005-entrega-1`.
