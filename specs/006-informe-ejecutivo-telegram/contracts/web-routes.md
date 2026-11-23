# Contrato — Rutas web de 006

**Convenciones**: HTML con Jinja2; HTMX solo dentro de una sección; respuestas de error con
`partials/error.html` y `role="alert"`. Toda ruta de caso impone `case_id` en la consulta y devuelve
404 si el caso o el recurso no pertenece a él. Las acciones externas nunca ocurren en un `GET`.

## Navegación

- Administración → «Contactos y canales»: `/settings/contacts`.
- Caso → «Informe ejecutivo»: `/cases/{case_id}/reports`.
- Caso → «Informes y notificaciones»: `/cases/{case_id}/notifications`.
- La barra lateral muestra ambas entradas del caso y la de administración.

## Informe ejecutivo (Corte A)

### `GET /cases/{case_id}/reports`

Lista versiones del caso: identificador, fecha, snapshot, autor, estado de síntesis, enlace a web y
PDF. Si no hay snapshot confirmado, muestra «Sin importaciones confirmadas» y no permite generar.

### `GET /cases/{case_id}/reports/new`

Formulario: selector de snapshot confirmado (por defecto el último), filtros opcionales, política de
contenido, `synthesis` (`off` por defecto / `on` si el proveedor está disponible) y autor declarado.
Muestra la base y advierte que la generación no envía nada.

### `POST /cases/{case_id}/reports`

Valida snapshot confirmado y filtros; crea `report_version` y encola la generación. Responde `303` a
la versión creada. Errores: `422` con mensaje y el formulario conservado; nunca crea informe desde
staging, rechazo, cancelación o vista previa.

### `GET /cases/{case_id}/reports/{report_id}/versions/{version}`

Vista web: cabecera (caso, alcance, identificador, fecha, snapshot, filtros), resumen, tarjetas,
gráficas interactivas con tabla alternativa, focos, recomendaciones con procedencia, limitaciones y
cobertura, y acciones «Descargar PDF» / «Preparar envío». Si la síntesis no está disponible, muestra
el rótulo «Sin síntesis de IA».

### `GET /cases/{case_id}/reports/{report_id}/versions/{version}/pdf`

Devuelve `application/pdf` con `Content-Disposition: attachment`; el archivo es el artefacto
persistido. Si el PDF no existe o está en generación, responde `409` con estado y no genera al vuelo.

### `GET /cases/{case_id}/reports/{report_id}/versions/{version}/preview`

Vista previa de impresión (HTML) para revisión visual; no es el PDF y no dispara envíos.

## Confirmación y envío manual (Corte B)

### `POST /cases/{case_id}/reports/{report_id}/versions/{version}/confirmations`

Cuerpo: `contact_ids[]`, `content_policy` y `confirmed_by`. Valida contactos verificados, consentidos,
activos y vinculados al caso. Construye el manifiesto canónico `report-manifest-v1` con versión,
texto saliente, hash del PDF, política y destinatarios; guarda `manifest_json` y `manifest_sha256` en
`report_confirmation`. Responde `201` con el id y el manifiesto. Si un contacto no es válido o el PDF
no coincide, `422` y no crea confirmación.

### `POST /cases/{case_id}/reports/{report_id}/versions/{version}/notifications`

Cuerpo: `confirmation_id`, `contact_ids[]` y `mode=manual`. Recalcula el manifiesto y exige que
`manifest_sha256` coincida con la confirmación vigente; si no coincide, `409` con
`manifest_mismatch`. Crea o reutiliza un `notification_event` por contacto con la clave de
idempotencia, guarda el manifiesto ejecutado y encola la entrega. Responde `202` con los eventos y su
estado. Un doble envío devuelve los eventos existentes sin crear nuevos.

### `GET /cases/{case_id}/notifications`

Historial: informe/versión, modo, regla, destinatarios, contenido confirmado, estado por componente,
fechas e identificador de mensaje si existe. Distingue «preparado», «solicitado», «aceptado»,
«parcial», «fallido» e «incierto».

### `POST /cases/{case_id}/notifications/{event_id}/retry`

Solo para eventos `failed` o `partial`; reencola únicamente componentes no aceptados y crea un nuevo
intento. Un evento `uncertain` no se reintenta por esta ruta: exige revisión y una acción explícita
posterior.

## Contactos (Corte B)

### `GET /settings/contacts`

Lista alias, canal, tipo, estado, consentimiento, casos autorizados y última verificación. No muestra
`chat_id` completo ni token.

### `POST /settings/contacts`

Crea contacto `unverified`, `consent_status=pending`, `active=false`. Valida formato y evita
duplicados por `(channel, chat_id)`. No envía mensajes.

### `POST /settings/contacts/{contact_id}/verification`

**Envío del código**, solicitado explícitamente desde la interfaz. Es independiente del envío de
informes: funciona con `status=unverified` y no exige consentimiento ni vínculo al caso. Valida que
exista el contacto, el token y que no se supere el límite; consulta `getChat`/`getChatMember`, crea
`contact_verification_challenge` con hash, expiración, intentos y `bot_fingerprint`, y envía el
código. No crea `notification_event`. Errores: `bot_not_member`, `chat_not_found`, `rate_limited`,
`verification_locked`.

### `POST /settings/contacts/{contact_id}/verification/confirm`

Cuerpo: `code` y `verified_by`. Solo un desafío `pending`, no expirado y con intentos disponibles
puede consumirse. Si el código coincide, marca `consumed` y el contacto `verified`, registra fecha,
método y evidencia, y permite el consentimiento. Código inválido, expirado, consumido o bloqueado:
`422` con `code_invalid`, `code_expired`, `code_consumed` o `verification_locked`, sin cambiar el
estado del contacto.

### `POST /settings/contacts/{contact_id}/consent`

Cuerpo: `consent_status=granted|revoked` y `declared_by`. Registra `consent_at`. Revocar bloquea
envíos de inmediato.

### `POST /settings/contacts/{contact_id}/status`

Activa, desactiva o revoca. Nunca borra el historial de envíos.

### `POST /cases/{case_id}/contacts/{contact_id}`

Autoriza o revoca el vínculo contacto–caso. Sin vínculo autorizado no se puede confirmar ni enviar.

## Reglas automáticas (Corte C)

### `GET /cases/{case_id}/notification-rules`

Lista versiones y estado. La regla nueva está `draft` y desactivada por defecto.

### `POST /cases/{case_id}/notification-rules`

Crea una versión `draft` con disparador `qualys_import_confirmed`, condiciones, política de contenido,
`synthesis_policy=factual_only` por defecto, destinatarios y autor declarado. Calcula
`content_sha256`. No activa.

### `POST /cases/{case_id}/notification-rules/{rule_id}/activate`

Valida destinatarios verificados y consentidos, vínculo al caso, autor y hash de condiciones/política.
Marca `active` y registra fecha. Al dispararse, la regla construye el mismo manifiesto
`report-manifest-v1`, usa `generation_key = auto:<evaluation.id>` y conserva la versión generada.
Cualquier cambio de destinatarios, condiciones o política exige una versión nueva y reactivación.

### `POST /cases/{case_id}/notification-rules/{rule_id}/deactivate`

Marca `disabled`; los trabajos pendientes de esa regla se omiten con `reason_code=rule_disabled`.

## Errores y códigos

| Código HTTP | Uso |
|---|---|
| `404` | Caso o recurso fuera del alcance |
| `409` | Conflicto: PDF no listo, versión ya enviada, estado incompatible |
| `409` | `manifest_mismatch`: el contenido o los destinatarios cambiaron desde la confirmación |
| `422` | Validación de formulario, contacto no verificado, confirmación inválida, código inválido |
| `429` | Verificación o envío limitado por tasa |
| `503` | Renderizador o proveedor no disponible; no se crea artefacto parcial |

Los errores no incluyen token, chat completo, cabeceras, contenido del PDF ni datos de otro caso.
