# Revisión de 005, Entrega 2 — 2026-11-22

Podemos continuar en una sola ejecución: corregir los tres defectos siguientes y, si sus pruebas pasan, avanzar a la Entrega 3. La Entrega 2 todavía no está lista para pruebas externas de pago. Esta revisión no modifica código de producto ni acredita aceptación de 005.

## Evidencia revisada

- Rama: `005-generador-configurable`; último commit observado: `63e3dc6`.
- Reportes: `005-ultimo-resultado.md`, `handoff-005.md` y tareas de 005.
- Código: inicio y reintento de turnos, proveedores, transporte, autorización, presupuesto y uso.
- 58 pruebas seleccionadas de configuración, registro de proveedores, contexto, costos, ledger, autorización, herramientas externas, persistencia de uso y contratos HTTP: **58 passed**, 14 advertencias, 1,40 s.
- Comprobaciones adicionales con fixtures y HTTP simulado, sin APIs externas y sin modificar almacenamiento del usuario.

## Ajustes necesarios

| ID | Defecto confirmado | Evidencia y consecuencia |
|---|---|---|
| R1 | El reintento omite la autorización externa y el perfil del proveedor. | `conversation/retry.py:79–124` no consulta `ensure_external_allowed`; construye contexto del caso y deja `external_scope=None`. Una autorización `public_corpus` no conserva las restricciones de historial, documentos y herramientas que dependen de ese campo. Además, la ejecución se registra con el proveedor predeterminado `ollama`. |
| R2 | Los adaptadores externos ignoran el timeout recibido por llamada. | `deepseek.py` y `anthropic.py` reciben `timeout_seconds`, pero no lo pasan a `http_common.post_json`. Con timeout de perfil 12,5 s y llamada de 0,25 s, el transporte simulado recibió 12,5 s. El tiempo restante del turno no se aplica al transporte. |
| R3 | El inicio del turno no persiste todos los parámetros efectivos. | `conversation/turn.py:82–97` omite `generator_max_output_tokens`, `generator_timeout_seconds` y `external_authorization_id`. Con perfil de 64 tokens y 12,5 s, SQLite registra 1200 tokens, 90 s y autorización nula. La página puede presentar valores distintos de los usados. |

Comprobación adicional observada:

```text
initial_record: expected_output=64, stored_output=1200;
expected_timeout=12.5, stored_timeout=90.0; authorization_saved=False
retry_context: expected_scope=public_corpus, actual_scope=None;
recorded_provider=ollama; case_context_present=True
requested_timeout=0.25;
actual_transport_timeout={connect:12.5, read:12.5, write:12.5, pool:12.5}
```

No se observó una salida real de datos a un proveedor. R1 se confirmó construyendo el contexto del reintento; el riesgo de salida se identifica porque las restricciones del grafo usan `external_scope`.

## Único prompt para OpenCode

```text
/speckit.implement

Continúa la funcionalidad 005-generador-configurable en la rama actual. Aplica la estrategia de entregas completas: corrige defectos concretos, ejecuta sus pruebas y, si pasan, continúa con la Entrega 3 T035–T042 en esta misma ejecución. No reinicies planificación ni generes otra ronda de analyze por ajustes locales.

Lee AGENTS.md, la constitución canónica, los artefactos vigentes de 005, docs/planificacion/005-ultimo-resultado.md, docs/planificacion/handoff-005.md y docs/planificacion/revision-codex-005-entrega-2.md. Conserva los cambios del usuario. Los IDs citados corresponden exclusivamente a 005.

PRIMERO: CORREGIR LOS TRES DEFECTOS CONFIRMADOS

R1. Unifica las garantías de inicio y reintento de turno externo:
- start_retry_turn debe comprobar la autorización vigente del caso para el proveedor efectivo, antes de cualquier conteo remoto o llamada al modelo.
- Una autorización ausente o revocada bloquea el reintento. No heredes una autorización revocada ni amplíes su alcance.
- Propaga external_scope y external_authorization_id al contexto y al registro. Para public_corpus, excluye contexto privado, historial privado y evidencias del caso igual que en un turno nuevo; conserva el bloqueo de herramientas importadas.
- Registra proveedor, modelo, identidad y parámetros efectivos del intento nuevo. Reutiliza la pregunta original y conserva attempt_no/retry_of_run_id sin duplicar mensajes.
- Añade pruebas de reintento con public_corpus, autorización revocada/ausente, cambio de local a externo entre intentos y bloqueo de resultados importados. Comprueba cero llamadas externas, incluido el contador remoto, cuando no hay autorización; usa señuelos ficticios para verificar que no salen contexto, historial o fuentes privadas.

R2. Aplica el timeout efectivo en ambos adaptadores:
- Propaga timeout_seconds hasta la petición HTTP, acotado por el perfil y el tiempo restante del turno. No basta recibir el argumento.
- Prueba mediante MockTransport que una llamada con 0,25 s recibe ese límite aunque el cliente tenga 12,5 s.
- Conserva la clasificación timeout de llamada/turno, sin reintentos implícitos ni fallback. Una llamada de resultado incierto no libera la reserva como gasto cero.

R3. Corrige la evidencia de configuración:
- En inicio y reintento, persiste límite de salida, timeout, autorización, proveedor, modelo e identidad efectivos; no dejes valores predeterminados distintos del perfil seleccionado.
- Usa una prueba integral con valores deliberadamente diferentes: salida 64 tokens y timeout 12,5 s. Verifica SQLite y la vista de ejecución.
- No reescribas retrospectivamente ejecuciones históricas con valores supuestos.

Implementa pruebas de regresión que fallen antes de cada arreglo y pasen después. Reutiliza funciones comunes cuando reduzca la divergencia entre inicio y reintento. No dupliques el grafo.

DESPUÉS: ENTREGA 3 T035–T042

Si los arreglos anteriores pasan, continúa sin pedir otra confirmación:
- Congela diez preguntas públicas/ficticias con hash y expectativas antes de medir.
- Implementa el ejecutor y reportes JSON/Markdown de comparación previstos en las tareas.
- Mide Ollama real. Registra latencia del turno completo y de sus llamadas, uso, costo aplicable, estructura, citas y recomendaciones. Distingue comprobaciones automáticas de evaluación semántica no realizada. No atribuyas mejoras a un externo sin medirlas.
- Conserva las mismas preguntas, corpus y condiciones comparables; registra proveedor/modelo y configuración. No conviertas sugerencias de prioridad en etiquetas humanas ni entrenamiento.
- Prepara la comparación DeepSeek/Anthropic y pruébala con transporte simulado, diferenciándola explícitamente de mediciones reales.
- No ejecutes llamadas externas de pago en esta ejecución: esta instrucción no aporta un monto autorizado. No uses como aprobación los valores de ejemplo de configuración. Conserva la comparación externa pendiente con motivo concreto, incluso si encuentras una clave configurada.
- Mantén Ollama disponible por selección explícita, embeddings locales y Qdrant sin cambios. No envíes Qualys, sus derivados ni datos privados a APIs.
- Ejecuta make check y, al cierre de los cambios, la regresión de integración prevista para 005 y 001/002/004. No repitas una suite que ya pasó salvo nuevos cambios relevantes o fallos.
- Si cambias interfaz, valida el flujo afectado con Playwright; si no cambia, no rehagas la revisión visual completa.
- Marca completadas solo las tareas con evidencia. T039 real debe permanecer pendiente si no se ejecuta; T042 debe reflejar aceptación parcial o pendiente según el contrato, nunca aceptación externa ficticia.
- No inicies 006 ni retomes 003.

RESULTADOS EN ARCHIVOS

Guarda toda la evidencia revisable, sin depender de la consola:
- Actualiza docs/planificacion/005-ultimo-resultado.md y docs/planificacion/handoff-005.md.
- Guarda en docs/evidencia/005-entrega-3/ un informe con R1–R3, archivos cambiados, comandos y resultados observados, comparación Ollama real, pruebas externas simuladas y pendientes reales.
- Conserva los reportes de comparación en la ubicación prevista por tasks.md y enlázalos desde el informe.
- Sincroniza tasks.md, README, AGENTS y constitución cuando corresponda; corrige el encabezado de tasks.md que aún dice que ninguna tarea se ha ejecutado.
- No imprimas claves ni copies .env, CSV privado o bases del usuario al repositorio. Usa almacenamiento de prueba separado, sin alterar storage/ ni storage/demo.
- Crea commits locales revisables con pruebas y documentación; no hagas push ni crees remotos.

Finaliza indicando: defectos corregidos y pruebas que los acreditan, estado de T035–T042, rutas de reportes, comparación real realizada, motivo de omisión externa y siguiente dato necesario. Si aparece un bloqueo material, registra su evidencia y completa el trabajo independiente que siga siendo posible.
```
