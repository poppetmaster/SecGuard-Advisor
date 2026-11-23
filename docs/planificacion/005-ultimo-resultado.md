# 005 — Último resultado (aceptación local parcial; T039 pendiente)

**Fecha**: 2026-11-22 (America/Bogota, `-05`)
**Rama**: `005-generador-configurable`
**Estado**: T001–T038, T040–T042 y T043–T048 completadas; R1–R3 corregidos; T039 real pendiente.
**005 no tiene aceptación de proveedores externos.**

## Dictamen

R1–R3 están corregidos y acreditados con pruebas. La comparación local con Ollama real se ejecutó
sobre un conjunto congelado de diez preguntas ficticias: 8/8 citas esperadas, 2/2 abstenciones y una
latencia media de 13948 ms. La comparación DeepSeek/Anthropic se ejecutó solo con transporte simulado.
La comparación externa real no se ejecutó porque no hay presupuesto aprobado ni credenciales; no se
usan valores de ejemplo como aprobación.

## R1 — Reintento externo

- `start_retry_turn` comparte con el inicio `resolve_turn_profile`, `create_turn_record` y
  `build_turn_context`.
- Autorización vigente comprobada antes de cualquier conteo remoto o llamada.
- Ausente/revocada bloquea; no se hereda ni amplía.
- `external_scope` y `external_authorization_id` llegan al contexto y a `runs`.
- `public_corpus` excluye contexto del caso, historial y fuentes privadas.
- `findings_query` importado sigue bloqueado.
- El intento nuevo registra proveedor, modelo, identidad y parámetros efectivos; conserva pregunta,
  `attempt_no` y `retry_of_run_id`.

Evidencia: `tests/unit/test_retry_external_scope.py` — **6 passed** (cero llamadas sin autorización,
señuelos privados, cambio local→externo, importados bloqueados, vista).

## R2 — Timeout por llamada

- `post_json` aplica `timeout_seconds` a `client.post`.
- DeepSeek y Anthropic lo propagan; el nodo lo acota por perfil y tiempo restante.
- Pruebas con cliente 12,5 s y llamada 0,25 s confirman `read=0.25`.
- Sin reintentos implícitos; timeout conserva la reserva.

## R3 — Evidencia efectiva

- Inicio y reintento persisten salida máxima, timeout, autorización, proveedor, modelo e identidad
  desde el mismo perfil.
- Prueba integral con **64 tokens** y **12.5 s**: SQLite y la vista muestran esos valores.
- Las ejecuciones históricas conservan 1200/90; no se reescriben.

## Comparación (T035–T038)

- Conjunto congelado en `tests/fixtures/provider_comparison.py`; hash
  `92778d5cdffca49c065354a4c5e816d8af678c30ae795d5fd506ffe8db5c5129`; 10 preguntas (8 con cita
  esperada, 2 de abstención).
- Ejecutor `scripts/compare_providers.py` con JSON/Markdown.
- Pruebas del conjunto y ejecutor: `tests/unit/test_provider_comparison.py` — **4 passed**.

### Ollama real

`docs/evidencia/005-comparacion/ollama.json` y `ollama.md`:

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

Duraciones: 6929, 7738, 6816, 8008, 8114, 9666, 10216, 16992, 25881 y 39123 ms.
Recomendaciones declaradas: 1. `missing_info` declarados: 2.

### DeepSeek/Anthropic simulados

- `deepseek-mock.json` / `.md`: 10 turnos, costo calculado simulado 0.000810 USD.
- `anthropic-mock.json` / `.md`: 10 turnos, costo calculado simulado 0.000600 USD.
- No son mediciones reales; no acreditan calidad ni latencia de los proveedores.

### T039 real

Pendiente: `deepseek-real-pending.json` y `anthropic-real-pending.json` registran «Sin presupuesto
externo aprobado (external_budget_usd=0)». No se usaron claves ni se hizo ninguna llamada paga.

## T040 — Regresión

```text
make check
  → 649 passed, 37 deselected, 17 warnings

make test-integration
  → 37 passed, 649 deselected, 14 warnings (1213.60 s = 20:13)
```

La primera ejecución de integración falló en `test_qualys_import_real` porque el prompt de decisión
no repetía una consulta con filtro distinto; se corrigió (`decide-v6`), la prueba pasó y la suite
completa quedó verde. No se relajaron criterios ni se ampliaron tiempos.

## T042 — Aceptación

**Aceptación local parcial**: Ollama real, comparación local, R1–R3, `make check` y
`make test-integration` verdes. **Proveedores externos no aceptados**: solo contratos simulados;
T039 real pendiente. T042 registra aceptación parcial, no integral.



## Configuración de IA desde la interfaz (T043–T048)

- Ruta `/settings/ai`, en el grupo **Administración** del menú general, fuera de un caso y disponible en escritorio y móvil. El grupo no implica autenticación ni roles.
- Selección de proveedor, modelo, máximo de salida (solo externos) y timeout; guardado en SQLite mediante
  `ai_configuration` y `ai_provider_profiles` (migración `f7a8b9c0d1e2`).
- Precedencia: configuración guardada > `Settings`/`.env`; `.env` conserva claves, endpoints y
  presupuestos y no se modifica. `SECGUARD_GENERATION_MODEL` vacío usa el modelo predeterminado.
- Perfiles independientes por proveedor; cambiar de proveedor no arrastra modelos ni sobrescribe
  parámetros de otro.
- Ollama no exige clave ni presupuesto monetario; su reserva de salida es automática dentro del
  contexto técnico y se muestra «Ejecución local; sin cobro por tokens de API». No se afirma costo
  operativo cero.
- Los límites externos se validan contra el proveedor/modelo seleccionado; cambiar de proveedor no
  arrastra modelos ni altera consultas en curso.
- Cada turno usa una instantánea; una consulta en curso conserva su perfil. Los reintentos usan la
  autorización vigente y registran los parámetros efectivos.
- Los recursos propios del turno (generador, contador, embeddings e índice) se cierran en éxito,
  error y fallo de preparación; no se cierran recursos inyectados o compartidos.
- El formulario muestra presupuestos global/por turno, moneda y «Clave configurada»/«Clave
  pendiente»; nunca valores, fragmentos ni máscaras. Conexión: «No verificada».
- Un externo con presupuesto cero muestra «Configurado; consultas externas bloqueadas hasta
  autorizar presupuesto». Guardar no autoriza gasto ni envía datos.
- No hay llamadas externas ni conteo remoto al abrir o guardar.

Pruebas nuevas: `tests/unit/test_ai_config_service.py` (9), `tests/contract/test_ai_settings_routes.py`
(12) y `tests/unit/test_ai_config_turn.py` (4); cierre de recursos (3). Playwright validó escritorio y móvil, guardado,
cambio de perfiles, mensajes, foco, Escape, ausencia de overflow y consola sin errores. Capturas en
`docs/evidencia/005-configuracion-ui/`.

`make check`: **677 passed**, 37 deselected.

## Limitaciones

- Evaluación semántica no realizada; solo comprobaciones automáticas.
- Corpus de comparación ficticio; no representa datos del usuario.
- Ollama: costo de API no aplicable; no se declara costo operativo total cero.
- Sin llamadas reales a DeepSeek/Anthropic.
- La configuración guardada no verifica la conexión; solo declara credencial presente.
- No se enviaron Qualys, derivados ni datos privados.
- `storage/`, `storage/demo`, Chroma y Qdrant sin cambios.
- `LANGSMITH_TRACING=false`.

## Archivos cambiados

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

Ver `git log --oneline` en `005-generador-configurable`.
