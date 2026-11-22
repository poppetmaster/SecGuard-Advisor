# Handoff — 005 Generador configurable (Entregas 1–3)

**Fecha**: 2026-11-22
**Estado**: R1–R3 corregidos; T001–T038 y T040–T042 completadas; T039 real pendiente; 005 con aceptación local parcial.
**Rama**: `005-generador-configurable`.

## 1. Correcciones R1–R3

### R1 — Reintento externo

- Inicio y reintento comparten `resolve_turn_profile`, `create_turn_record` y `build_turn_context`.
- `start_retry_turn` comprueba autorización vigente antes de crear la ejecución o contar tokens.
- Autorización ausente/revocada bloquea; no se hereda ni se amplía.
- `external_scope` y `external_authorization_id` se propagan al contexto y a `runs`.
- `public_corpus` excluye contexto del caso, historial y fuentes privadas.
- `findings_query` importado sigue bloqueado.
- Evidencia: `tests/unit/test_retry_external_scope.py` — 6 passed.

### R2 — Timeout por llamada

- `post_json` recibe `timeout_seconds` y lo aplica a `client.post`.
- DeepSeek y Anthropic lo propagan.
- Pruebas con cliente 12,5 s y llamada 0,25 s: `read=0.25`.
- Sin reintentos implícitos; timeout conserva la reserva.

### R3 — Evidencia efectiva

- Inicio y reintento persisten salida máxima, timeout, autorización, proveedor, modelo e identidad.
- Prueba con 64 tokens y 12,5 s; SQLite y vista muestran esos valores.
- Ejecuciones históricas no se reescriben.

## 2. Comparación (T035–T038)

- Conjunto congelado: `tests/fixtures/provider_comparison.py`; hash
  `92778d5cdffca49c065354a4c5e816d8af678c30ae795d5fd506ffe8db5c5129`; 10 preguntas.
- Ejecutor: `scripts/compare_providers.py`.
- Ollama real: `docs/evidencia/005-comparacion/ollama.json` / `.md`.
  - 10 turnos, 8 respondidas, 8/8 citas esperadas, 2/2 abstenciones, media 13948 ms, 1 recomendación,
    2 `missing_info`, costo API no aplicable, evaluación semántica no realizada.
- DeepSeek/Anthropic mock: `deepseek-mock.*`, `anthropic-mock.*`, costos simulados 0.000810/0.000600
  USD. No son mediciones reales.

## 3. T039 — Pendiente real

- `deepseek-real-pending.json` y `anthropic-real-pending.json`:
  «Sin presupuesto externo aprobado (external_budget_usd=0).»
- No se usaron claves ni se hicieron llamadas pagas.

## 4. Estado de tareas

- T001–T038: completadas.
- T039: pendiente la ejecución real; simulación ejecutada.
- T040: completada — `make check` 649 passed; `make test-integration` 37 passed (1213.60 s).
- T041: documentación.
- T042: completada como aceptación local parcial; externos no aceptados.

## 5. Siguiente dato necesario

Presupuesto externo autorizado (global y por turno) y credenciales locales para ejecutar T039 real.
Después: revalidar modelos/precios y repetir la comparación con el mismo conjunto congelado.

## 6. Límites

- Sin evaluación semántica; solo comprobaciones automáticas.
- Corpus ficticio; no datos del usuario.
- No se enviaron Qualys, derivados ni datos privados.
- `storage/`, `storage/demo`, Chroma y Qdrant sin cambios.
- `LANGSMITH_TRACING=false`.
