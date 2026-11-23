# Panel «Uso y comparativos de IA»

**Objetivo**: consultar y comparar el uso registrado de Ollama, DeepSeek y Claude desde la
aplicación, con telemetría por solicitud, agregados, filtros, comparativo de evaluaciones y evidencia.
**Rama**: `005-generador-configurable` (el panel pertenece a 005; no inicia 006).
**Entrega**: persistencia, instrumentación, consultas, interfaz, pruebas y evidencia.

## Specs

- **S1. Reutilización.** Se reutilizan `runs`, `run_steps`, `run_tool_calls`, `provider_usage` y
  `provider_budget_ledger`. No se crea otra fuente que contradiga esos registros ni se reescriben
  ejecuciones anteriores.
- **S2. Unidades.** «Consulta» es un turno (`runs`). «Llamada al modelo» es una operación lógica
  (`decide`, `generate`, `repair`). «Solicitud API» es un intento HTTP enviado a un proveedor
  externo. «Reintento» es un nuevo intento de la misma operación lógica. «Llamada local» es una
  inferencia con Ollama y no es solicitud API externa. `findings_query` no cuenta como solicitud a
  un proveedor de IA.
- **S3. Registro por solicitud.** Migración aditiva `ai_requests` con: id local, `run_id`, operación,
  intento y `retry_of_request_id`, proveedor/modelo efectivos, `started_at`/`finished_at` UTC, estado
  (`completed`, `error`, `timeout`, `uncertain`), duración, tokens de entrada/salida/caché/escritura
  de caché, tokens de razonamiento y `reasoning_included_in_output`, fuente de uso (`observed`,
  `estimated`, `unavailable`), costo calculado, costo informado por el proveedor solo con evidencia,
  moneda, versión y vigencia de tarifa, `evaluation_id` y `scenario`. Sin claves, cabeceras, prompts
  ni respuestas.
- **S4. Sin duplicados.** Una fila por intento lógico; clave única `(run_id, operation, attempt_no)`.
  Un callback repetido no inserta dos veces. Los reintentos del turno se leen de
  `runs.attempt_no`/`retry_of_run_id`.
- **S5. Tokens y dinero.** Los tokens de caché no se suman otra vez a la entrada. Los tokens de
  razonamiento no se suman otra vez si están incluidos en la salida. Dinero con `Decimal`. La tarifa
  histórica se conserva y no se recalcula. Una reserva no es gasto. Timeout no es costo cero.
- **S6. Ollama.** Se muestra «Sin cobro por API», conservando tokens y duración disponibles. No se
  afirma costo operativo total cero. Sin medición se muestra «No disponible».
- **S7. Filtros.** Fechas (America/Bogota, almacenamiento UTC, límites inclusivos por día local),
  proveedor, modelo, operación, estado, ámbito (`general`/`evaluation`) y evaluación concreta.
  Período visible y acción para limpiar.
- **S8. Panel.** Ruta bajo Administración, debajo de Configuración de IA, fuera de un caso. Tarjetas:
  costo calculado USD, solicitudes API externas, llamadas locales, tokens de entrada/salida,
  consultas, latencia mediana del turno. Cobertura observada/estimada/no disponible y reservas
  pendientes separadas. Gráficas por día: costo, solicitudes/l lamadas por proveedor, tokens.
  Tabla accesible equivalente. Tabla por proveedor/modelo con consultas, llamadas, solicitudes
  externas o locales, éxitos/errores, reintentos, tokens, caché, latencia mediana, costo calculado,
  costo medio por consulta y cobertura. Detalle paginado por ejecución con operaciones y enlace a la
  evidencia existente.
- **S9. Gráficas locales.** Sin CDN. Se usa SVG/HTML generado por Jinja2, sin nueva dependencia.
- **S10. Comparativo.** Selector de evaluación; proveedores/modelos; escenarios ejecutados; éxito,
  abstención correcta y exactitud de herramientas; validez automática de citas; latencia mediana;
  tokens y solicitudes; costo total y por escenario; calidad registrada. Solo escenarios comunes;
  muestra incompleta identificada. Distingue automático, asistido por IA y revisión humana
  registrada. La validez de citas no se presenta como respaldo semántico. Sin ganador inventado.
- **S11. Importación histórica.** `ai_evaluations` y `ai_evaluation_results` con procedencia,
  versión y `detail_level`. Importación explícita e idempotente desde `casos.json` y
  `resultados-<proveedor>.json`. No se fabrican solicitudes desde agregados. Se marca «Histórico
  agregado». Los registros sin métricas se muestran incompletos, no como consumo cero.
- **S12. Privacidad.** Ver y filtrar no invoca modelos ni gasta. No hay botón para lanzar
  evaluaciones ni consultas a facturación. Sin claves ni identificadores sensibles. Administración no
  implica autenticación.
- **S13. Pruebas.** Cubre decisión/generación/reparación, reintentos sin duplicación, timeout con
  costo desconocido, caché sin doble conteo, tarifa histórica, reservas separadas, Ollama separado,
  límites de fecha, medianas y denominadores, históricos incompletos, importación idempotente,
  escenarios comunes, ausencia de secretos y migración aditiva.

## Tasks

- [x] T1 Pruebas RED de telemetría: éxito, timeout, error, incierto, caché, Ollama, reintento,
  evaluación y ausencia de secretos. `tests/unit/test_ai_usage_telemetry.py`.
- [x] T2 Migración aditiva y modelos `AiRequest`, `AiEvaluation`, `AiEvaluationResult`.
  `alembic/versions/*_add_ai_requests_evaluations.py`, `src/secguard_advisor/db/models.py`.
- [x] T3 Instrumentación única en `provider_call`; mapeo de estado, uso, costo y deduplicación.
  `src/secguard_advisor/conversation/providers/usage.py`, `ai_usage/telemetry.py`.
- [x] T4 Servicio de agregados, filtros, cobertura, medianas y comparativo.
  `src/secguard_advisor/ai_usage/queries.py`, `service.py`.
- [x] T5 Importación idempotente y CLI. `src/secguard_advisor/ai_usage/evaluation_import.py`,
  `scripts/import_evaluation_005.py`.
- [x] T6 Rutas y plantillas: panel, pestañas, tarjetas, SVG accesible, tablas, detalle paginado,
  estados vacíos e incompletos. `src/secguard_advisor/web/routes/ai_usage.py`,
  `web/templates/ai_usage/`.
- [x] T7 Navegación «Uso y comparativos de IA» debajo de Configuración de IA.
- [x] T8 Pruebas de agregados, fechas, importación idempotente, comparativo y contrato de rutas.
- [x] T9 Sembrador ficticio para evidencia. `scripts/seed_ai_usage_demo.py`.
- [x] T10 Playwright: Administración, filtros, tarjetas, gráficas, tablas, detalle, vacíos,
  390/320 px, teclado, consola y cero llamadas a proveedores.
- [x] T11 Evidencia y documentación en `docs/evidencia/005-panel-uso-ia/`; actualizar
  `005-ultimo-resultado.md`, `handoff-005.md`, `README.md`, `AGENTS.md` y tareas 005.
- [x] T12 `make check`, integraciones afectadas y commits locales.

## Log

- **L1 (solicitud original, 2026-11-23)**: «Implementa en SecGuard Advisor el panel “Uso y
  comparativos de IA”, disponible desde Administración en el menú principal. Primero lee AGENTS.md,
  la constitución vigente, los artefactos de 005 y el informe de la evaluación de proveedores que
  acaba de terminar. Conserva sus resultados y reutiliza la instrumentación existente. […] Entrega
  este ajuste como un bloque funcional completo: persistencia, instrumentación, consultas agregadas,
  interfaz, pruebas y evidencia. […] Realiza commits locales con código, migración, pruebas y
  documentación. No hagas push ni inicies Telegram o la funcionalidad 003.»
- **L3 (cierre)**: `make check` con 707 passed; integraciones afectadas con 8 passed; Playwright
  validó escritorio, 390 px, 320 px, teclado y ausencia de solicitudes a proveedores. La evidencia
  está en `docs/evidencia/005-panel-uso-ia/`.
- **L2 (decisiones de diseño)**: se reutilizan `runs`/`provider_usage`/ledger; `ai_requests` añade
  detalle por intento HTTP sin contradecirlos. El histórico sin filas de solicitud se agrega desde
  `runs` y se marca incompleto. La evaluación actual se importa como histórico agregado desde JSON,
  sin fabricar solicitudes. Las gráficas se generan como SVG/HTML en Jinja2, sin dependencia nueva.
- **L4 (corrección de exactitud, 2026-11-23)**: se separó consumo completo (incluye bloqueados)
  del comparativo funcional sobre la muestra común de 9 escenarios. Costo conocido DeepSeek
  0,006201 USD (incluye S08) y Anthropic 0,006150 USD (incluye S08), con 2 y 3 registros
  desconocidos. Los adaptadores capturan uso antes de validar y reinician `last_usage`; la salida
  inválida conserva tokens/costo cuando hay evidencia. Informes regenerados y Playwright verificado.
