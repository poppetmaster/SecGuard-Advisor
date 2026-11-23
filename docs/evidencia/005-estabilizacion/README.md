# Estabilización 005 — tiempos, salidas estructuradas y S10

**Fecha**: 2026-11-23
**Rama**: `005-generador-configurable`
**Alcance**: estabilización acotada; sin llamadas pagadas nuevas y sin iniciar 006.

## 1. Diagnóstico y correcciones

### 1.1 Tiempos excedidos de Ollama

**Causa concreta:** el cliente de Ollama recibía un `timeout` de httpx por lectura, no un
presupuesto total de la llamada. Una respuesta que entrega contenido de forma gradual podía superar
los 90 s por llamada y los 120 s de turno; el plazo solo se comprobaba después de que la llamada
terminara. Los registros históricos muestran S02 con 136 618 ms y S04 con 182 842 ms.

**Corrección:**

- `_DeadlineTransport` en `conversation/llm.py` envuelve el transporte de Ollama y corta la lectura
  al vencer el plazo total de la llamada.
- `_model_timeout` no inicia una llamada si quedan menos de 1 s; el tool no inicia si quedan menos
  de 0,5 s.
- Se conservan los límites de 90 s por llamada y 120 s por turno; no se aumentaron.
- Timeout de llamada → `model_timeout`; plazo restante del turno → `run_timeout`.
- La reserva y el uso desconocido se conservan; una respuesta tardía no se persiste como éxito.

**Evidencia:** `timeout-local-ollama.txt`. Prueba local con timeout de 0,5 s: estado `timeout`,
código `model_timeout`, 3 656 ms observados (incluye preparación/cierre), sin esperar 136 s.
La prueba determinista de `_DeadlineStream` está en `tests/unit/test_llm_client.py`.

**Límite:** cerrar la conexión HTTP no garantiza que Ollama detenga la inferencia en el servidor. El
comportamiento observado es que la aplicación deja de esperar y no persiste una respuesta tardía;
no se afirma cancelación del cómputo local. El permiso global de generación se libera cuando termina
la espera local; si Ollama sigue infiriendo, la aplicación no inicia dos generaciones locales
simultáneas y Ollama serializa la siguiente solicitud, pero no hay confirmación de cancelación del
trabajo del servidor.

### 1.2 Salidas estructuradas externas

**Causa observada en la evidencia histórica:** DeepSeek S03/S04 y Anthropic S02–S04 registraron
`invalid_model_output` con 13/19 tokens de salida y respuesta vacía. No se conservó el
`finish_reason`/`stop_reason` ni el contenido crudo, por lo que los archivos no permiten distinguir
de forma concluyente entre truncamiento, JSON inválido y esquema incumplido. El límite de salida era
1200 tokens, muy superior a 13/19: la evidencia **no sostiene** que el límite de salida sea la causa.

**Correcciones:**

- El uso se captura antes de validar el JSON y se reinicia por llamada; ya estaba corregido y se
  conserva.
- El parser busca el primer objeto JSON completo, en lugar de recortar entre el primer `{` y el
  último `}`; acepta texto alrededor y bloques cercados sin aceptar estructuras incorrectas.
- `AnswerPayload`, `Claim` y `ToolDecision` usan `extra="forbid"`; un campo inventado no se convierte
  en éxito.
- `InvalidModelOutput.reason` diferencia `empty_content`, `json_invalid`, `schema_mismatch` y
  `truncated_content`. El motivo seguro se registra en `error_message`; no se guardan claves ni
  contenido privado.

**Evidencia:** `tests/unit/test_http_common.py`,
`tests/contract/test_deepseek_adapter.py`, `tests/contract/test_anthropic_adapter.py`,
`tests/contract/test_chat_routes.py`.

**Pendiente real:** no se ejecutaron llamadas externas nuevas. No existe una autorización nueva
explícita para gastar en esta estabilización; la comprobación real de DeepSeek/Anthropic queda
pendiente. No se presenta la infraestructura simulada como aceptación real.

### 1.3 S10 e informe breve

**Causa concreta:** la recuperación global exige `retrieval_min_score=0.5033`. Para la pregunta de
síntesis, los fragmentos de respaldo y accesos obtuvieron puntuaciones 0.399, 0.326 y 0.251; el
filtro dejó `hits=0`. El modelo recibió cero fuentes y se abstuvo. No fue una limitación del modelo.

**Corrección acotada:**

- Solo para preguntas de informe/resumen/síntesis, si la recuperación normal queda vacía, se
  reintenta la recuperación sin el umbral y se conservan únicamente fragmentos `case_evidence`.
  El umbral global no cambia.
- El prompt `chat-v9` indica que un informe debe ser breve, separar recomendaciones propuestas de
  controles implementados y declarar limitaciones; si hay evidencia parcial, responder con ella.
- Al persistir un informe se agregan las recomendaciones como propuestas y las limitaciones. Si el
  modelo no declaró limitaciones, se añade una limitación estándar (evidencia recuperada, no
  certificación ni auditoría).
- Se conserva la abstención cuando no hay evidencia.

**Antes/después local (Ollama real, caso ficticio):**

| Métrica | Antes | Después |
|---|---|---|
| Recuperación S10 | 0 hits | 2 hits `case_evidence`, estado `expanded_case` |
| Resultado | `insufficient_evidence` | `answered` |
| Contenido | Abstención | Resumen, 4–5 claims, 3 recomendaciones y limitación |
| Duración del turno | — | 44 631 ms (agente 35 710 ms, dentro de 90 s por llamada) |

**Evidencia:** `s10-local-ollama.txt`, `ui-s10-respuesta.png`, `tests/unit/test_limits.py`.

**Límite:** la latencia de S10 quedó cerca del límite de 90 s por llamada; una corrida posterior
puede agotar el tiempo. No se aumentó el límite. La variabilidad de la máquina local sigue siendo
una limitación real.

### 1.4 Anthropic S07 y respuestas con herramienta

**Causa concreta:** `findings_query` devolvía un resultado correcto, pero el modelo añadía claims
documentales inválidos. El grafo exigía persistir sin claims cuando había evidencia de herramienta;
al haber claims, enviaba a reparación y luego a abstención.

**Corrección:** una respuesta **exclusivamente** de herramienta (sin claims documentales) puede
persistir con `findings_query` `ok`. Si hay claims documentales rechazados, se conserva la
reparación/abstención; no se eliminan silenciosamente ni se presentan como verificados. La salida
anticipada que persistía con cualquier cita válida se corrigió: ahora una cita válida junto con una
rechazada pasa por reparación y, si sigue rechazada, abstiene. Las pruebas cubren tool-only, mixta
inválida, mixta con citas válidas, citas parcialmente rechazadas y herramienta fallida/vacía.

**Evidencia:** `tests/unit/test_qualys_conversation.py`,
`tests/unit/test_limits.py` y `ui-chat-completo.png` (findings_query con total y grupos).

### 1.5 T039

- Marker `external` registrado en `pyproject.toml`.
- `make check` excluye `external`; `make test-external` los ejecuta aparte.
- `tests/external/test_external_readiness.py` omite con motivo si falta
  `SECGUARD_EXTERNAL_TESTS_AUTHORIZED=1`, presupuesto o credenciales. No envía solicitudes.
- `pytest -m external`: 1 skipped, 785 deselected.
- T039 **no está cerrado**: la infraestructura está lista, pero no hay aceptación externa real
  nueva. Tampoco se presenta la prueba omitida como evaluación real.

## 2. Pruebas ejecutadas

- `make check`: **748 passed**, 38 deselected.
- Integraciones afectadas (`test_ollama_provider_regression`, `test_answer_real`,
  `test_tool_only_question`, `test_midturn_failure`, `test_trace_and_fallback`): **8 passed**
  (76,07 s).
- `pytest -m external`: **1 skipped** con motivo explícito.
- S10 local real y timeout local real: ver archivos de evidencia.
- No se hicieron llamadas pagadas y no se modificó la evidencia original de los 30 escenarios.

## 2.1 Reevaluación externa focalizada

La pasada autorizada de DeepSeek/Claude está separada en
`docs/evidencia/005-estabilizacion/reevaluacion-externa/`. Consumo: 0,010526 USD conocidos,
0,010870 USD de ledger, dentro del tope adicional de 0,10 USD. DeepSeek S10 aprobado; las seis
generaciones fallidas consumieron 1 200 tokens de salida y se clasificaron como `schema_mismatch` o
`truncated_content`. No se aumentó el límite ni se cambió el criterio. T039 y la aceptación externa
siguen pendientes; no se avanza a 006.

## 2.2 Reevaluación con salida 4096

La pasada separada `reevaluacion-externa-4096/` configuró 4096 tokens para perfiles externos y
consumió 0,013628 USD autorizados (0,014512 USD de ledger, incluyendo un S10 extra no solicitado).
DeepSeek S04 y Claude S04/S10 aprobaron; S03 falla por el criterio existente, S02 por citas
rechazadas y S07 ejecutó `findings_query` pero terminó insuficiente. T039 y la aceptación externa
siguen pendientes; no se avanza a 006.

## 2.3 S07 y S03 posteriores

- **S07:** el fallback determinista de `findings_query` está implementado y probado: muestra filtros,
  total, grupos, origen e instantánea con la etiqueta «Resultado de herramienta; síntesis del modelo
  no disponible». No se ejecutó una llamada nueva; la evidencia real 4096 conserva el fallo previo.
- **S03:** recálculo separado `005-s03-bilingual-v2` sobre respuestas conservadas; el criterio
  histórico no se modifica y los dos resultados se muestran en `s03-bilingue/`.
- **Validación de plan externo:** `scripts/reevaluate_external_005.py` rechaza antes de llamar
  cualquier pareja fuera de DeepSeek S03/S04 y Claude S02/S03/S04/S07/S10; DeepSeek S10 tiene prueba
  específica de rechazo.

## 3. Capturas

- `ui-configuracion-proveedor.png`
- `ui-s10-cargando.png`
- `ui-s10-respuesta.png`
- `ui-timeout-error.png`
- `ui-timeout-reintento.png`
- `ui-ejecucion-timeout.png`
- `ui-consumo-coherente.png`
- `ui-chat-completo.png`

## 4. Pendientes reales

- T039: falta autorización explícita y una ejecución externa afectada; no se declara aceptado.
- Salidas externas: la corrección de parser/diagnóstico está probada con dobles; la reproducción
  real de DeepSeek/Anthropic sigue pendiente.
- Tiempos de Ollama: el plazo total ya se aplica; la latencia local de S10 puede acercarse al
  límite de 90 s y no se aumentó.
- S10: resuelto en la corrida local, pero sujeto a la variabilidad del modelo local.
- Informe breve: la salida incluye recomendaciones y limitaciones; no certifica cumplimiento.
- No se inició Telegram ni 003.
