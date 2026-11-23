# Panel «Uso y comparativos de IA» — evidencia

**Fecha**: 2026-11-23 (America/Bogota)
**Rama**: `005-generador-configurable`
**Ruta**: `/settings/ai/usage`, dentro de **Administración**, debajo de Configuración de IA.

## Qué se implementó

- Telemetría por solicitud en `ai_requests`, con una fila por intento lógico de decisión,
  generación o reparación (y `remote_count` reservado para un conteo remoto futuro).
- Migración aditiva `a3c4d5e6f7a8_add_ai_requests_and_evaluations`; no reescribe ejecuciones
  anteriores.
- Instrumentación única en `provider_call`, reutilizando `runs`, `provider_usage` y
  `provider_budget_ledger`.
- Agregados por día, proveedor/modelo y ejecución; filtros por fecha, proveedor, modelo, operación,
  estado, ámbito y evaluación.
- Pestaña **Comparativo de pruebas** con evaluación importada, escenarios comunes, muestra
  incompleta, métricas automáticas, calidad asistida por IA y revisión humana registrada.
- Importación explícita e idempotente del informe de evaluación 005.
- Gráficas SVG/HTML generadas por Jinja2, sin CDN ni dependencia nueva.

## Definiciones y fórmulas

| Unidad | Definición |
|---|---|
| Consulta | Turno iniciado por el usuario; una fila de `runs`. |
| Llamada al modelo | Operación lógica registrada en `ai_requests` (`decide`, `generate`, `repair`). |
| Solicitud API | Intento de `ai_requests` cuyo proveedor es DeepSeek o Anthropic. |
| Reintento | Ejecución con `runs.attempt_no > 1`; se conserva `retry_of_run_id`. |
| Llamada local | Intento de `ai_requests` con proveedor Ollama. No es solicitud API. |
| Reserva pendiente | `provider_budget_ledger.state = 'reserved'`. |
| Reserva incierta | `state = 'reconciled'`; se muestra como compromiso separado. |

- **Costo calculado**: suma de `ai_requests.cost_usd` con `cost_status='calculated'`. Si una
  ejecución no tiene detalle, se usa `runs.cost_usd` solo si su estado es `calculated`.
- **Tokens**: suma de valores disponibles. `cached_tokens` se muestra aparte y no se suma otra vez
  a la entrada. `reasoning_tokens` se conserva y no se suma si `reasoning_included_in_output` es
  verdadero.
- **Latencia mediana del turno**: mediana de `runs.duration_ms` no nulos.
- **Tokens por día y proveedor**: agrupados por fecha local de America/Bogota a partir de
  `ai_requests.started_at`; una ejecución sin detalle aporta sus totales desde `runs`.
- **Costo / consulta**: costo calculado dividido por consultas del mismo proveedor/modelo.
- **Cobertura**: conteo de solicitudes `observed`, `estimated`, `unavailable` y ejecuciones
  históricas sin telemetría por solicitud.
- **Éxito de evaluación**: aprobados / ejecutados (los bloqueados no cuentan como ejecutados).
- **Abstención correcta**: `abstention_ok = true` sobre filas con ese dato.
- **Exactitud de herramientas**: `findings_match = true` sobre filas con ese dato.
- **Validez automática de citas**: citas aceptadas por el validador / citas emitidas. No prueba
  respaldo semántico.
- **Escenarios comunes**: intersección de escenarios entre proveedores. La muestra común ejecutada
  excluye bloqueados o no ejecutados.

## Esquema de persistencia

```text
ai_requests
  id, run_id, operation, attempt_no, retry_of_request_id,
  provider, model, started_at, finished_at, status, duration_ms,
  input_tokens, output_tokens, cached_tokens, cache_write_tokens,
  reasoning_tokens, reasoning_included_in_output, usage_source,
  cost_usd, cost_status, provider_reported_cost_usd, currency,
  tariff_version, tariff_effective_at, evaluation_id, scenario, error_code, created_at

ai_evaluations
  id, import_key, name, version, frozen_at, dataset_sha256, source,
  source_path, detail_level, provenance_json, imported_at

ai_evaluation_results
  id, evaluation_id, provider, model, scenario, kind, executed, result,
  outcome, error_code, duration_ms, input_tokens, output_tokens, cached_tokens,
  usage_source, cost_usd, cost_status, tariff_version,
  citations_emitted, citations_valid, citations_resolvable,
  findings_match, abstention_ok, quality_score, quality_method,
  manual_review, run_id, detail_level, created_at
```

No se guardan claves, cabeceras de autorización, prompts, respuestas ni argumentos de herramientas.
La evidencia existente se enlaza con `runs.id`.

## Tratamiento de datos anteriores

- Las ejecuciones previas conservan sus filas. Si no tienen `ai_requests`, el panel usa
  `runs.usage_*`, `runs.cost_*` y `runs.duration_ms` y las marca como **histórico sin detalle**.
- Un dato no reconstruible se muestra como `—` o «No disponible»; nunca como cero.
- El informe de la evaluación 005 se importó como **histórico agregado**: crea
  `ai_evaluations`/`ai_evaluation_results`, no `ai_requests`, porque los JSON/CSV no permiten
  reconstruir solicitudes individuales.
- La importación es idempotente por `import_key = version:sha256`; una segunda ejecución actualiza
  las 30 filas sin duplicarlas.

## Comandos

```bash
uv run alembic upgrade head
make import-evaluation            # importa docs/evidencia/005-evaluacion-proveedores
uv run python scripts/import_evaluation_005.py --storage-dir storage/demo
uv run python scripts/seed_ai_usage_demo.py --storage /ruta/temporal/storage
```

## Pruebas ejecutadas

- `make check`: **707 passed**, 37 deselected.
- Integraciones afectadas:
  `test_ollama_provider_regression`, `test_answer_real`, `test_tool_only_question`,
  `test_midturn_failure`, `test_trace_and_fallback`: **8 passed** (90.84 s).
- Nuevas pruebas: telemetría (10), agregados y comparativo (6), importación (3), migración (1),
  contrato de rutas (5).
- Sin llamadas pagadas para probar el panel.

## Validación en navegador

Instancia temporal sembrada con datos ficticios (`scripts/seed_ai_usage_demo.py`), servidor local y
Playwright:

- Acceso por **Administración**; enlace debajo de Configuración de IA.
- Filtros aplicados y período visible; error controlado con fecha inicial posterior a la final.
- Tarjetas, cobertura, reservas separadas, gráficas con tabla accesible, tabla por proveedor/modelo,
  detalle paginado y enlace «Ver ejecución».
- Pestaña de comparativo con evaluación importada, escenarios comunes y muestra incompleta.
- Estados sin datos y con histórico incompleto.
- Escritorio 1280 px; móvil 390 px y 320 px sin desborde horizontal del documento.
- Navegación por teclado: enlace de salto, navegación, pestañas, campos y botones reciben foco;
  etiquetas asociadas por `for`/`id`.
- Consola: 0 errores y 0 advertencias.
- Red: solo peticiones a `127.0.0.1:8773` para la página y recursos estáticos; ninguna llamada a
  proveedores de IA.

Capturas:

- `panel-escritorio.png`
- `panel-filtros.png`
- `comparativo-pruebas.png`
- `panel-movil-390.png`
- `panel-movil-320.png`
- `panel-sin-datos.png`
- `panel-filtro-invalido.png`

## Privacidad y costos

- Ver y filtrar no crea generadores ni invoca modelos.
- No se consultaron APIs de facturación ni saldos.
- No se añadieron botones para lanzar evaluaciones.
- No se usaron datos Qualys privados; la evidencia es ficticia o pública.
- No se aumentaron presupuestos. La importación y el panel no generan gasto.
- Ollama se muestra como «Sin cobro por API»; no se declara costo operativo total cero.

## Limitaciones y pendientes

- Los datos previos a esta migración no tienen telemetría por solicitud; se muestran incompletos.
- El comparativo actual es histórico agregado y no permite reconstruir solicitudes.
- Una reserva de una ejecución terminal se reconcilia al arrancar y aparece como reserva incierta,
  no como pendiente; ambas categorías se muestran por separado.
- Los totales de tokens entre modelos no implican igual trabajo ni calidad.
- No hay revisión semántica humana registrada para la evaluación importada.
- El panel no es conciliación de factura ni de saldo del proveedor.
- Administración es una agrupación de navegación; no hay autenticación implementada.
- SC-001, SC-003 y la revisión en otros navegadores siguen pendientes.
