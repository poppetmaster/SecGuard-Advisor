# Handoff — 005 Generador configurable (Entregas 1–3)

**Fecha**: 2026-11-23 (actualizado tras la evaluación real)
**Estado**: R1–R3 corregidos; T001–T038, T040–T042 y T043–T048 completadas. La comparación externa
real se ejecutó; T039 queda parcialmente acreditada por el marker `external` y 005 mantiene
aceptación local, sin aceptación de proveedores externos.
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


## 2.1 Configuración de IA en la interfaz (T043–T048)

- Página `/settings/ai` en el grupo **Administración** del menú general, escritorio y móvil.
- Tablas `ai_configuration`/`ai_provider_profiles`; migración `f7a8b9c0d1e2`.
- Precedencia: guardado > `Settings`/`.env`; `.env` no se modifica.
- Perfiles independientes; instantánea por turno y reintento.
- Ollama sin clave, presupuesto ni cuota comercial; reserva de salida automática y mensaje local.
- Presupuestos externos informativos; claves solo como «Clave configurada»/«Clave pendiente».
- Límites externos validados por proveedor/modelo; recursos del turno cerrados en éxito, error y
  preparación fallida.
- Cero llamadas externas al abrir/guardar; sin conteo remoto.
- Evidencia y capturas: `docs/evidencia/005-configuracion-ui/`.
- `make check`: 677 passed.

## 2.2 Panel «Uso y comparativos de IA» (2026-11-23)

- Ruta `/settings/ai/usage` en Administración, debajo de Configuración de IA.
- Telemetría por solicitud en `ai_requests`; evaluación importada en
  `ai_evaluations`/`ai_evaluation_results`; migración aditiva `a3c4d5e6f7a8`.
- Importación idempotente: `make import-evaluation` (no crea solicitudes desde agregados).
- Evidencia, fórmulas y capturas: `docs/evidencia/005-panel-uso-ia/`.
- `make check`: 736 passed, 38 deselected; integraciones afectadas: 8 passed.
- Corrección de exactitud (2026-11-23): consumo completo incluye bloqueados; costo conocido
  DeepSeek 0,006201 USD y Anthropic 0,006150 USD, con 2 y 3 registros desconocidos. El comparativo
  funcional usa la muestra común de 9 escenarios (Ollama 5/9, DeepSeek 6/9, Anthropic 4/9).
- Gráficas interactivas con Apache ECharts 5.6.0 (Apache-2.0) servido localmente; exportación PNG,
  tooltips y tablas accesibles. Evidencia en `docs/evidencia/005-panel-uso-ia/`.
- Estabilización 2026-11-23: deadline total de Ollama, parser externo estricto con motivos,
  S10 con recuperación de respaldo para informes, S07 exclusivamente de herramienta persistido y
  marker `external` para T039. Evidencia en `docs/evidencia/005-estabilizacion/`.
- Pendiente real sin cambios: aceptación externa/T039, reproducción externa de salidas, variabilidad
  de latencia de Ollama y revisión semántica de S10.

## 3. T039 — Comparación externa real

- Ejecutada el 2026-11-23 con claves y presupuestos existentes (5 USD global / 5 USD por turno), sin
  aumentarlos ni modificar `.env`.
- Conjunto congelado `005-evaluation-v1` (10 escenarios), instancia temporal, corpus público y caso
  ficticio. Evidencia en `docs/evidencia/005-evaluacion-proveedores/`.
- Ollama: 6/10 aprobados; DeepSeek: 6/9 (S08 bloqueado); Anthropic: 4/9 (S08 bloqueado).
- Costo conocido (incluye S08 bloqueado): DeepSeek 0,006201 USD; Anthropic 0,006150 USD. Ledger acumulado 0,025515 USD;
  restante conservador 4,974485 USD.
- S08 queda bloqueado en externos por `external_tool_blocked`; es el comportamiento esperado.
- Defecto pendiente: Ollama supera los límites declarados (S02 136 618 ms, S04 182 842 ms).
- **T039 no se cierra**: falta registrar el marker `external` de pytest y su omisión sin credencial.

## 4. Estado de tareas

- T001–T038: completadas.
- T050–T055 (panel de uso): completadas.
- T039: ejecución real registrada; criterio del marker `external` pendiente.
- T040: completada — `make check` y `make test-integration` verdes en el corte anterior; repetir
  `make check` tras los cambios de esta evaluación.
- T041: documentación actualizada.
- T042: aceptación local parcial; externos no aceptados.

## 5. Siguiente dato necesario

Implementar el marker `external` de pytest con omisión sin credencial para cerrar T039. Después,
decidir si se corrige el exceso de timeout de Ollama y si se repite la comparación externa con más
escenarios. La aceptación externa requiere mejor calidad sostenida y revisión semántica.

## 6. Límites

- Sin evaluación semántica; solo comprobaciones automáticas.
- Corpus ficticio; no datos del usuario.
- No se enviaron Qualys, derivados ni datos privados.
- `storage/`, `storage/demo`, Chroma y Qdrant sin cambios.
- `LANGSMITH_TRACING=false`.
