# Tasks: Generador configurable (Ollama, DeepSeek y Claude Haiku)

**Input**: Documentos de diseño de `/specs/005-generador-configurable/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md y
checklists/requirements.md

**Tests**: incluidas porque la constitución aplica test-first cuando existe una prueba determinista y
un resultado esperado claro.

**Estado**: planificación. Ninguna tarea ejecutada, ninguna dependencia instalada, ninguna llamada
pagada realizada y ninguna aceptación declarada. Las tareas externas quedan condicionadas a
credencial y presupuesto explícitos.

## Formato

```text
- [ ] TNNN [P?] [US?] Descripción con archivo o comando concreto
  - Story: Setup|Foundational|US1..US4|Polish
  - Dep: dependencias explícitas o none
  - Verifies: tarea de implementación que evalúa (solo pruebas y verificaciones)
  - Check: comprobación observable
  - Evidence: archivo, diff, salida o reporte requerido
```

`[P]` significa que puede ejecutarse en paralelo con otra tarea de la misma entrega porque no comparte
archivos editables y sus dependencias ya están completas.

## Path Conventions

- Código: `src/secguard_advisor/`
- Pruebas: `tests/unit/`, `tests/contract/`, `tests/integration/`, `tests/acceptance/`
- Scripts: `scripts/`
- Documentación: `docs/`, `specs/005-generador-configurable/`

---

## Entrega 1 — Configuración y contrato común, conservando Ollama

**Cierre de la entrega:** la aplicación arranca con `ollama` sin cambios funcionales; una
configuración externa incompleta falla con un mensaje claro; el generador se selecciona una vez; el
esquema de herramienta es tipado y el proveedor/modelo se registra por ejecución.

- [x] T001 [P] [US1] Añadir pruebas de configuración: selección de proveedor, precedencia entorno >
  `.env` > predeterminados, credencial ausente, proveedor desconocido y límites inválidos.
  - Story: Foundational
  - Dep: none
  - Verifies: T002
  - Check: fallan antes de implementar; cubren cada mensaje de error sin imprimir valores.
  - Evidence: `tests/unit/test_provider_config.py` con salida RED.

- [x] T002 [US1] Extender `Settings` con proveedor, modelo, límite de salida, timeout, razonamiento,
  `SecretStr` para DeepSeek/Anthropic, presupuesto y versión de tarifa.
  - Story: Foundational
  - Dep: T001
  - Check: T001 pasa; `ollama` no exige credencial; un proveedor externo sin credencial falla cerrado.
  - Evidence: `src/secguard_advisor/config.py`, pruebas verdes.

- [x] T003 [P] [US1] Actualizar `.env.example` con marcadores vacíos y verificar que `.env` sigue
  ignorado por Git.
  - Story: Foundational
  - Dep: T002
  - Verifies: T002
  - Check: la plantilla no contiene claves reales; `git check-ignore .env` lo confirma.
  - Evidence: `.env.example`, salida de `git check-ignore`.

- [x] T004 [P] [US1] Añadir pruebas del protocolo común y del registro de proveedores: selección
  explícita, sin fallback, identidad y cierre.
  - Story: US1
  - Dep: T002
  - Verifies: T005
  - Check: fallan antes de implementar; un proveedor desconocido no cae a Ollama.
  - Evidence: `tests/unit/test_provider_registry.py` con salida RED.

- [x] T005 [US1] Implementar `ProviderProtocol`, `ProviderIdentity` y `ProviderRegistry` con
  `provider`, `model`, `identity`, `decide`, `generate`, `last_usage` y `close`.
  - Story: US1
  - Dep: T004
  - Check: T004 pasa; el grafo recibe el generador por inyección y no conoce el proveedor.
  - Evidence: `src/secguard_advisor/conversation/providers/{base,registry}.py`.

- [x] T006 [P] [US1] Añadir pruebas del esquema tipado de `ToolDecision.arguments` y de la
  compatibilidad con `FindingsArguments`, incluido el rechazo de campos extra y la ausencia de
  `case_id`.
  - Story: US1
  - Dep: T005
  - Verifies: T007
  - Check: fallan antes de implementar; los valores inválidos no llegan a la herramienta.
  - Evidence: `tests/unit/test_tool_decision_schema.py` con salida RED.

- [x] T007 [US1] Sustituir `ToolDecision.arguments: dict` por un esquema tipado y acotado compatible
  con `findings_query`; adaptar el generador Ollama y los consumidores.
  - Story: US1
  - Dep: T006
  - Check: T006 pasa; el comportamiento de `findings_query` no cambia; la salida estructurada de
    Ollama sigue funcionando.
  - Evidence: `src/secguard_advisor/conversation/llm.py`, `tools/findings.py`, pruebas verdes.

- [x] T008 [P] [US1] Añadir pruebas de migración y de registro por ejecución: proveedor, identidad,
  límites, uso y costo inicial.
  - Story: US1
  - Dep: T005
  - Verifies: T009
  - Check: una fila previa se rellena con `ollama`; una ejecución nueva registra el proveedor
    seleccionado.
  - Evidence: `tests/integration/test_provider_run_record.py` con salida RED.

- [x] T009 [US1] Crear la migración aditiva de `runs` y actualizar `create_run`/`turn.py` para
  registrar proveedor, identidad y límites.
  - Story: US1
  - Dep: T008
  - Check: T008 pasa; las filas previas conservan sus datos; `alembic upgrade head` es reversible.
  - Evidence: migración Alembic, `src/secguard_advisor/evidence/runs.py`, `conversation/turn.py`.

- [x] T010 [P] [US1] Añadir una prueba de contrato de la página de ejecución que muestre proveedor y
  modelo sin secretos.
  - Story: US1
  - Dep: T009
  - Verifies: T011
  - Check: la página muestra `ollama` y el modelo; no muestra claves.
  - Evidence: `tests/contract/test_run_provider_view.py` con salida RED.

- [x] T011 [US1] Actualizar `runs/show.html` y la vista para mostrar proveedor, modelo, identidad y
  límites.
  - Story: US1
  - Dep: T010
  - Check: T010 pasa; la evidencia existente sigue visible.
  - Evidence: plantilla y vista, pruebas verdes.

- [x] T012 [P] [US1] Añadir la regresión local real de Ollama: consulta con citas, memoria y
  herramienta, sin cambios funcionales.
  - Story: US1
  - Dep: T009
  - Verifies: T005, T007, T009
  - Check: pasa con Ollama y Qdrant locales; no requiere credencial externa.
  - Evidence: `tests/integration/test_ollama_provider_regression.py`.

- [x] T013 [P] [US1] Añadir la prueba de ausencia de fallback: un fallo externo no intenta Ollama y
  un fallo local no intenta externo.
  - Story: US1
  - Dep: T005
  - Verifies: T005
  - Check: el código de error conserva el proveedor seleccionado; no hay segunda llamada.
  - Evidence: `tests/unit/test_no_provider_fallback.py`.

- [x] T014 [US1] Documentar la entrega 1 y su criterio de cierre en
  `docs/planificacion/005-ultimo-resultado.md`.
  - Story: US1
  - Dep: T012, T013
  - Check: el documento distingue implementado de planificado.
  - Evidence: sección de entrega 1.

---

## Entrega 2 — Adaptadores externos y controles de datos, contexto y costos

**Cierre de la entrega:** DeepSeek y Anthropic funcionan contra un servidor simulado y, con
credencial/presupuesto, contra el proveedor real en pruebas condicionadas; el contexto se mide por
proveedor; el presupuesto reserva y liquida; el contenido privado se bloquea; no hay secretos en
logs/SQLite/trazas.

- [x] T015 [P] [US2] Añadir pruebas de contrato de DeepSeek: JSON Output, contenido vacío, uso,
  error de autenticación, 429 y timeout.
  - Story: US2
  - Dep: T005
  - Verifies: T016
  - Check: fallan antes de implementar; usan un servidor HTTP simulado, sin llamada pagada.
  - Evidence: `tests/contract/test_deepseek_adapter.py` con salida RED.

- [x] T016 [US2] Implementar el adaptador DeepSeek con `httpx`, `response_format=json_object`,
  razonamiento desactivado por defecto y normalización de errores/uso.
  - Story: US2
  - Dep: T015
  - Check: T015 pasa; el contenido vacío se clasifica como `invalid_model_output`.
  - Evidence: `src/secguard_advisor/conversation/providers/deepseek.py`.

- [x] T017 [P] [US2] Añadir pruebas de contrato de Anthropic: `output_config.format`, respuesta
  estructurada, `count_tokens`, autenticación, 429 y timeout.
  - Story: US2
  - Dep: T005
  - Verifies: T018
  - Check: fallan antes de implementar; no realizan llamadas reales.
  - Evidence: `tests/contract/test_anthropic_adapter.py` con salida RED.

- [x] T018 [US2] Implementar el adaptador Anthropic con `json_schema`, `effort` bajo, omisión de
  parámetros de muestreo y normalización de errores/uso.
  - Story: US2
  - Dep: T017
  - Check: T017 pasa; el esquema Pydantic se transforma y se valida localmente.
  - Evidence: `src/secguard_advisor/conversation/providers/anthropic.py`.

- [x] T019 [P] [US3] Añadir pruebas de admisión de contexto por proveedor: GGUF en Ollama,
  `count_tokens` en Anthropic, estimador conservador en DeepSeek, reducción y fallo mínimo.
  - Story: US3
  - Dep: T016, T018
  - Verifies: T020
  - Check: fallan antes de implementar; la pregunta y el contexto declarado no se recortan.
  - Evidence: `tests/unit/test_provider_context.py` con salida RED.

- [x] T020 [US3] Implementar `PromptCounter` por proveedor y conectarlo a `budget.plan_prompt`.
  - Story: US3
  - Dep: T019
  - Check: T019 pasa; Ollama conserva su tokenizador; el conteo externo respeta la compuerta de
    privacidad.
  - Evidence: `conversation/providers/context.py`, `conversation/budget.py`.

- [x] T021 [P] [US3] Añadir pruebas del cálculo de costo: tramos de Anthropic, peak/off-peak y caché
  de DeepSeek, uso faltante = `unknown`, Ollama = `not_applicable`.
  - Story: US3
  - Dep: T016, T018
  - Verifies: T022
  - Check: fallan antes de implementar; nunca se inventa cero.
  - Evidence: `tests/unit/test_provider_cost.py` con salida RED.

- [x] T022 [US3] Implementar la tabla de tarifas versionada y el cálculo de costo/uso.
  - Story: US3
  - Dep: T021
  - Check: T021 pasa; la tarifa registra fecha, fuente y versión.
  - Evidence: `conversation/providers/cost.py`.

- [x] T023 [P] [US3] Añadir pruebas del libro de presupuesto: reserva antes de enviar, bloqueo por
  saldo, liquidación, liberación y reconciliación tras reinicio.
  - Story: US3
  - Dep: T022
  - Verifies: T024
  - Check: fallan antes de implementar; no se duplica gasto.
  - Evidence: `tests/unit/test_budget_ledger.py` con salida RED.

- [x] T024 [US3] Implementar `provider_budget_ledger`, reserva/liquidación y reconciliación de
  arranque.
  - Story: US3
  - Dep: T023
  - Check: T023 pasa; `external_budget_usd=0` bloquea toda llamada externa.
  - Evidence: migración, `evidence/budget.py`, pruebas verdes.

- [x] T025 [P] [US2] Añadir pruebas de autorización externa: bloqueo sin autorización, permiso con
  `public_corpus`/`fictional_case`, revocación y rechazo de `private_case`.
  - Story: US2
  - Dep: T005
  - Verifies: T026
  - Check: fallan antes de implementar; la credencial sola no autoriza.
  - Evidence: `tests/unit/test_external_authorization.py` con salida RED.

- [x] T026 [US2] Implementar `ExternalProcessingAuthorization` y la compuerta previa a cualquier
  llamada externa o conteo externo.
  - Story: US2
  - Dep: T025
  - Check: T025 pasa; el error es `external_processing_blocked`.
  - Evidence: `db/models.py`, `cases/external.py`, migración.

- [x] T027 [P] [US2] Añadir pruebas de `findings_query` con proveedor externo: permitido solo para
  `fictional_case` + `origin=synthetic`; bloqueo de importados/mixtos y ausencia de Qualys en el
  prompt.
  - Story: US2
  - Dep: T026
  - Verifies: T028
  - Check: fallan antes de implementar; un resultado importado bloquea antes de ejecutar.
  - Evidence: `tests/unit/test_external_tool_block.py` con salida RED.

- [x] T028 [US2] Implementar la compuerta de `findings_query` externa (`fictional_case` +
  `origin=synthetic`), `external_tool_blocked` y la instrucción de usar Ollama para hallazgos
  importados.
  - Story: US2
  - Dep: T027
  - Check: T027 pasa; nunca se envía un resultado importado ni una fila Qualys.
  - Evidence: `conversation/nodes.py`, `web/errors.py`.

- [x] T029 [P] [US2] Añadir pruebas de redacción y escaneo de secretos en logs, SQLite, trazas,
  errores y capturas.
  - Story: US2
  - Dep: T016, T018
  - Verifies: T030
  - Check: fallan antes de implementar; una clave ficticia no aparece en ningún artefacto.
  - Evidence: `tests/unit/test_secret_redaction.py` con salida RED.

- [x] T030 [US2] Centralizar la redacción de secretos, rutas y cabeceras; aplicarla a errores,
  logs, trazas y evidencia.
  - Story: US2
  - Dep: T029
  - Check: T029 pasa; no se registra la clave ni el cuerpo del proveedor.
  - Evidence: `conversation/providers/redaction.py`, `evidence/tracing.py`.

- [x] T031 [P] [US3] Añadir una prueba de contrato de la página de ejecución con uso y costo:
  calculado, desconocido y no aplicable, sin secretos.
  - Story: US3
  - Dep: T024, T030
  - Verifies: T032
  - Check: la página muestra la tarifa y el estado; nunca muestra la clave.
  - Evidence: `tests/contract/test_run_usage_view.py` con salida RED.

- [x] T032 [US3] Actualizar `runs/show.html` y la vista con proveedor, uso, tarifa y costo.
  - Story: US3
  - Dep: T031
  - Check: T031 pasa; la evidencia histórica no cambia.
  - Evidence: plantilla y vista.

- [x] T033 [P] [US2] Añadir la prueba de independencia de LangSmith: activar proveedor externo no
  habilita trazas ni envía contenido.
  - Story: US2
  - Dep: T030
  - Verifies: T030
  - Check: `LANGSMITH_TRACING=false` permanece; el tracer recibe solo metadatos.
  - Evidence: `tests/unit/test_langsmith_independence.py`.

- [x] T034 [US2] Documentar la entrega 2 y sus límites en `005-ultimo-resultado.md` y
  `docs/planificacion/handoff-005.md`.
  - Story: US2
  - Dep: T024, T030, T032, T033
  - Check: distingue simulado, real condicionado y no ejecutado.
  - Evidence: secciones de entrega 2.

---

## Entrega 3 — Comparación, regresión y documentación final

**Cierre de la entrega:** comparación reproducible con Ollama real y externos condicionados;
regresión completa verde; documentación final y decisión de aceptación basada en evidencia.

- [ ] T035 [P] [US4] Crear el conjunto fijo de diez preguntas públicas/ficticias y su hash, antes de
  medir.
  - Story: US4
  - Dep: T034
  - Check: el conjunto no contiene datos privados ni Qualys; el hash queda registrado.
  - Evidence: `tests/fixtures/provider_comparison.py`.

- [ ] T036 [P] [US4] Añadir pruebas del ejecutor de comparación: mismas preguntas, métricas,
  separación medición/expectativa y omisión sin credencial/presupuesto.
  - Story: US4
  - Dep: T035
  - Verifies: T037
  - Check: fallan antes de implementar; una omisión no se presenta como resultado.
  - Evidence: `tests/unit/test_provider_comparison.py` con salida RED.

- [ ] T037 [US4] Implementar `scripts/compare_providers.py` con reporte JSON/Markdown.
  - Story: US4
  - Dep: T036
  - Check: T036 pasa; el reporte incluye latencia, citas, estructura, recomendaciones y costo.
  - Evidence: script y pruebas verdes.

- [ ] T038 [US4] Ejecutar la comparación local real con Ollama y registrar los resultados medidos.
  - Story: US4
  - Dep: T037
  - Check: no requiere credencial externa; el reporte separa mediciones de expectativas.
  - Evidence: `docs/evidencia/005-comparacion/ollama.json` y resumen.

- [ ] T039 [US4] Ejecutar la comparación externa solo si hay credencial y presupuesto explícitos;
  si faltan, omitir con motivo. Registrar el marker `external` en la configuración de pytest.
  - Story: US4
  - Dep: T038
  - Check: no se simula; el motivo queda en el reporte; `pytest -m external` se omite sin credencial.
  - Evidence: reporte por proveedor o registro de omisión, `pyproject.toml`.

- [ ] T040 [US4] Ejecutar la regresión completa y la aceptación de los flujos afectados:
  `make check`, `make test-integration`, incluida la regresión de 001/002, la integración local de
  Ollama y la aceptación ASGI de selección/evidencia.
  - Story: Polish
  - Dep: T038, T039
  - Check: las puertas pasan; las externas no ejecutadas se reportan como omitidas; una omisión no
    acredita el criterio.
  - Evidence: salida de comandos, `tests/acceptance/`, reporte.

- [ ] T041 [US4] Actualizar `README.md`, `AGENTS.md`, la constitución (decisión de mantener Ollama
  junto a los proveedores externos), `005-ultimo-resultado.md` y `handoff-005.md` con el estado real.
  - Story: Polish
  - Dep: T040
  - Check: ningún documento presenta un proveedor externo como aceptado sin evidencia; no se
    inventan presupuestos ni aprobaciones.
  - Evidence: diffs y enlaces.

- [ ] T042 [US4] Declarar la aceptación de 005 solo si la evidencia de T040/T039 lo permite;
  conservar abiertas las tareas externas no ejecutadas.
  - Story: Polish
  - Dep: T041
  - Check: la aceptación distingue lo medido de lo omitido; `CONSTITUTION.md` sigue siendo el enlace
    simbólico.
  - Evidence: informe de aceptación y diff de constitución.

---

## Dependencias y orden

- **Entrega 1** es independiente y entrega valor por sí sola: selección configurable con Ollama.
- **Entrega 2** depende de la 1 (protocolo, configuración, esquema tipado).
- **Entrega 3** depende de la 2 (adaptadores y controles) y de la 1 (registro).
- Las tareas de prueba se escriben antes de su implementación y `Verifies` identifica la tarea
  evaluada.
- Las tareas externas (T015–T018 en simulado; T039 en real) no se ejecutan sin credencial y
  presupuesto. Una omisión no acredita el criterio correspondiente.

## Fuera de alcance

- Otros proveedores, Telegram, informes nuevos, P1–P4 y formulario de administración.
- Cambios en embeddings, Qdrant, Qualys o datos existentes.
- Llamadas pagadas durante la preparación.
