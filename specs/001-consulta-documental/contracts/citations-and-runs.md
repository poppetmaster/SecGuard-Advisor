# Contrato de citas, ejecuciones y trazas

## 1. Cita

### Estructura mostrada al usuario

```json
{
  "document_title": "The NIST Cybersecurity Framework (CSF) 2.0",
  "origin": "public_corpus",
  "version_label": "NIST CSWP 29 (2024-02-26)",
  "page": 12,
  "section": "GOVERN",
  "quote": "…",
  "locator": "/cases/{case_id}/documents/{document_id}/versions/{version_id}/fragments/{chunk_id}?quote=…",
  "status": "valid",
  "version_notice": null,
  "support_review": {
    "status": "unreviewed",
    "reviewed_by": null,
    "reviewed_at": null,
    "note": null
  }
}
```

- `origin`: `public_corpus` o `case_evidence`. Se muestra la etiqueta en español.
- `version_notice`: `null` o «versión superada» cuando la cita apunta a una versión anterior.
- `status`: `valid` o `unavailable`. Una cita `rejected` nunca llega a la interfaz.

### Control 1 — existencia y localización (automático)

1. El `chunk_id` existe en `document_chunks`.
2. La versión del fragmento coincide con la versión citada.
3. El documento pertenece al caso autorizado o al corpus público.
4. `page` o `section` coinciden con los metadatos del fragmento.
5. `quote` aparece literalmente en el texto del fragmento tras normalizar: NFKC, colapso de
   espacios, guiones suaves eliminados, comparación sin distinguir mayúsculas.
6. `quote` no excede 400 caracteres y no está vacío.

Si cualquiera falla: `check_status='rejected'`, se guarda `check_reason` y la cita no se muestra.

### Control 2 — respaldo semántico (humano)

Una persona revisa que el fragmento sostenga la afirmación. Se registra en
`message_citations.support_review_status` con autor y fecha.

El producto no declara este control como cumplido. Es exactamente la corrección propuesta a
SC-003 en `plan.md`: la compuerta automática es el control 1; el control 2 se acredita por
revisión.

### Comportamiento sin evidencia

| Situación | Resultado |
|---|---|
| Recuperación sin candidatos documentales | El agente se ejecuta igual y puede usar la herramienta de hallazgos |
| Respuesta solo con evidencia estructurada de herramienta | `outcome=answered`, sin citas documentales |
| Resultado de herramienta con total 0 | `outcome=answered` sobre el registro consultado; no afirma ausencia de vulnerabilidades |
| Sin candidatos, sin herramienta y sin citas | `outcome=insufficient_evidence` |
| Candidatos débiles | El agente responde; si no cita, se intenta una reparación |
| Reparación sin citas válidas | `outcome=abstained_invalid_citations` |
| Cita a fragmento inexistente | Se descarta, se registra y se intenta reparar |
| Fuentes contradictorias | La respuesta expone la contradicción y no elige una sin declararlo |

El umbral de recuperación filtra candidatos débiles; no demuestra que no exista evidencia. Una cita
que pasa el control automático no acredita fundamentación: el respaldo semántico se revisa y se
registra por una persona.

Una recuperación documental vacía no cierra el turno si la herramienta de hallazgos puede responder.
Un resultado válido de total 0 responde sobre el registro consultado; no demuestra ausencia de
vulnerabilidades ni riesgo bajo. Las cifras sobre hallazgos deben corresponder a la invocación
registrada, no a una estimación del modelo.

## 2. Ejecución

### Estructura

```json
{
  "run_id": "…",
  "attempt_no": 1,
  "retry_of_run_id": null,
  "status": "succeeded",
  "outcome": "answered",
  "started_at": "2026-11-08T18:40:12Z",
  "duration_ms": 18400,
  "model": {
    "name": "qwen3.5:9b",
    "digest": "56671c2ab938",
    "num_ctx": 8192,
    "temperature": 0.1,
    "seed": 42
  },
  "embedding": { "name": "embeddinggemma", "dim": 768 },
  "prompt_version": "chat-v4",
  "steps": [
    { "name": "load_scope", "origin": "deterministic", "status": "ok", "duration_ms": 4 },
    { "name": "retrieve", "origin": "deterministic", "status": "ok", "duration_ms": 210 },
    { "name": "decide", "origin": "model", "status": "ok", "duration_ms": 1800 },
    { "name": "tools", "origin": "deterministic", "status": "ok", "duration_ms": 4 },
    { "name": "agent", "origin": "model", "status": "ok", "duration_ms": 15100 },
    { "name": "validate", "origin": "deterministic", "status": "ok", "duration_ms": 8 }
  ],
  "sources": [
    { "origin": "public_corpus", "rank": 1, "score": 0.81, "used_in_answer": true },
    { "origin": "case_evidence", "rank": 2, "score": 0.74, "used_in_answer": true }
  ],
  "tool_calls": [
    {
      "tool": "findings_query",
      "origin": "model_requested",
      "status": "ok",
      "arguments": { "severity": "Critical", "group_by": "asset" },
      "summary": { "total": 3 }
    }
  ],
  "trace": { "status": "submitted", "id": "…", "url": "https://…" },
  "error": null
}
```

### Estados

| `status` | Significado |
|---|---|
| `running` | En curso |
| `succeeded` | Terminó con respuesta o abstención |
| `failed` | Error de modelo, herramienta o interno |
| `timeout` | Excedió el tiempo de turno |
| `interrupted` | El proceso se reinició durante la ejecución |

| `outcome` | Significado |
|---|---|
| `answered` | Respuesta con al menos una cita válida **o** evidencia estructurada válida de herramienta |
| `insufficient_evidence` | Sin citas válidas, sin evidencia de herramienta y sin candidatos sobre el umbral |
| `abstained_invalid_citations` | Se abstuvo tras fallar la reparación |
| `error` | No se produjo respuesta |

### Reintentos y transacciones

- Un turno tiene un mensaje de pregunta y una o más ejecuciones (`attempt_no`). El mensaje de
  respuesta pertenece a la ejecución que terminó con respuesta.
- **Respuesta, citas, controles, pasos, fuentes, herramientas y cierre de la ejecución se
  persisten en una sola transacción.** No existe un estado donde la respuesta esté visible y la
  ejecución siga abierta.
- Si esa transacción falla, no hay respuesta persistida; la ejecución queda `failed` o, si tampoco
  se puede cerrar, `interrupted` al reiniciar.
- La ejecución se crea en una transacción corta antes de llamar al modelo. **Ninguna transacción
  permanece abierta durante la generación.**
- Hay dos controles: una ejecución `running` por caso (índice único parcial) y un semáforo global
  de una generación en el proceso. Una segunda consulta del mismo caso se rechaza; una de otro caso
  espera de forma acotada o recibe `429`.
- La desconexión del cliente no libera la ejecución ni el semáforo antes del cierre real.
- Al reiniciar, las ejecuciones `running` pasan a `interrupted` y liberan el caso.
- Los checkpoints viven en otra base. No hay atomicidad entre bases: los mensajes son la fuente
  autoritativa y el checkpoint se reconcilia (recorta o reconstruye) antes de cada turno.

### Traza

| `trace_status` | Significado | Qué se muestra |
|---|---|---|
| `disabled` | Sin credenciales o traza desactivada | «Traza no configurada» |
| `submitted` | Enviada sin error observado tras el envío y `flush`; el SDK no informó error | «Enviada (no verificada)», identificador y enlace a la traza |
| `confirmed` | La traza se observó en LangSmith durante la aceptación | «Traza verificada» con enlace |
| `failed` | Error de red o de API | «Traza no disponible» y motivo |

`confirmed` solo lo escribe `scripts/confirm_trace.py`, que recibe el `run_id` local y el
identificador de traza, consulta LangSmith en modo lectura y actualiza la fila únicamente si la
traza existe. La confirmación es responsabilidad de la persona que ejecuta la aceptación, y queda
registrada con su identidad, la fecha y la evidencia de la traza observada (salida del comando e
identificador). El código de la aplicación nunca escribe `confirmed`: como máximo `submitted`.

El código **nunca** marca una traza como verificada. `submitted` significa «enviada», no
«confirmada». La confirmación se hace en LangSmith durante la aceptación.

### Errores

| `error_code` | Cuándo |
|---|---|
| `model_unavailable` | Ollama no responde o el modelo no está instalado |
| `model_timeout` | Se agotó el tiempo de 90 s de una llamada al modelo |
| `run_timeout` | Se agotó el tiempo de 120 s del turno, incluida la decisión de herramienta |
| `step_limit` | Se excedió el máximo de 8 operaciones de modelo o herramienta |
| `tool_call_limit` | Se solicitaron más de dos llamadas a herramientas; las adicionales no se ejecutan y el turno puede responder con lo obtenido |
| `tool_failed` | Falló la consulta a la base de hallazgos |
| `tool_timeout` | La consulta de hallazgos excedió su tiempo |
| `context_budget_unavailable` | No se pudo cargar el tokenizador del generador |
| `context_budget_exceeded` | El prompt mínimo no cabe en el presupuesto |
| `invalid_model_output` | La salida no cumple el esquema tras la reparación |
| `citation_rejected` | Todas las citas de la respuesta fueron rechazadas |
| `internal_error` | Fallo no clasificado |

## 3. Revisión humana del respaldo semántico

| Estado | Significado | Qué se muestra |
|---|---|---|
| `unreviewed` | Nadie la revisó todavía | «Respaldo pendiente de revisión» |
| `supported` | Una persona comprobó que el fragmento sostiene la afirmación | «Revisado: respaldada por {autor}» |
| `not_supported` | Una persona comprobó que no la sostiene | «Revisado: no respaldada» y la observación |

Reglas:

- Autor y fecha los pone el servidor. El autor se toma de `SECGUARD_REVIEWER_NAME`; si está vacío,
  la revisión se rechaza con `409` y no se escribe la fila.
- `SECGUARD_REVIEWER_NAME` es una identidad local declarada, no autenticación.
- La observación es opcional y tiene un máximo de 500 caracteres.
- La revisión no adjudica prioridades P1–P4 ni aprueba informes.
- Una cita con `unreviewed` no se presenta como fundamentada, aunque su control automático sea
  `valid`.
- La revisión es por cita, no por respuesta completa.

## 4. Qué observa el usuario

- En la conversación: pregunta, respuesta, citas y un enlace «Ver ejecución».
- En la ejecución: modelo, digest, parámetros, prompt, duración, estado, intentos y vínculo con el
  anterior, pasos con su origen, fuentes recuperadas, herramientas con su origen, presupuesto de
  contexto registrado, citas con control automático y revisión humana por separado, errores y estado
  de la traza con su enlace cuando está disponible.
- En una ejecución fallida: el motivo comprensible y el acceso al reintento de la misma pregunta.
- El detalle de herramienta recalcula filas actuales solo si el contrato lo pidió; se rotula como
  «consulta actual» y nunca se presenta como el detalle histórico preservado.
- Nunca: credenciales, rutas del sistema de archivos, trazas de pila ni contenido de otro caso.
