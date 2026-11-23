# Contrato — Verificación y entrega por Telegram

**Canal único**: Telegram Bot API. **Token**: `TELEGRAM_BOT_TOKEN` en `.env` (`SecretStr`), nunca en
SQLite, interfaz, logs, evidencia ni LangSmith. `TELEGRAM_API_BASE_URL` permite un doble local en
pruebas; por defecto `https://api.telegram.org`.

## Dos envíos distintos

| Envío | Requisitos | Persistencia |
|---|---|---|
| Código de verificación | token, contacto existente, límite de solicitudes | `contact_verification_challenges` |
| Informe | contacto `verified`, consentimiento `granted`, vínculo `authorized`, regla/confirmación y manifiesto vigentes | `notification_events` + componentes + intentos |

El bloqueo de informes **no** bloquea el envío del código. Un contacto no verificado debe poder
recibir el código; de lo contrario nunca podría verificarse. El código no crea un
`notification_event`.

## Verificación del destino (no basta un chat_id)

Estados del contacto: `unverified → verified → revoked|disabled`.

1. **Registro**: alias + `chat_id` + tipo. El sistema valida formato y que no exista duplicado
   `(telegram, chat_id)`. Estado inicial `unverified`, consentimiento `pending`, `active=false`.
2. **Consulta**: `getMe` para identificar el bot (solo se guarda su hash) y `getChat` para confirmar
   existencia y tipo. En grupos/canales, `getChatMember` confirma que el bot pertenece al chat. Un
   fallo deja `unverified` con código seguro.
3. **Desafío persistido**: `contact_verification_challenges` guarda `code_sha256`, `bot_fingerprint`,
   `purpose=contact_verification`, `status`, `created_at`, `expires_at` (10 minutos), `attempts`,
   `max_attempts=3`, `request_count`, `window_started_at`, `last_sent_at` y `consumed_at`. El código
   en claro no se persiste ni se registra; el token tampoco.
4. **Código de un solo uso**: solicitado explícitamente desde la interfaz; `sendMessage` envía 6
   dígitos. Máximo 3 solicitudes por ventana. Un nuevo envío invalida el desafío anterior.
5. **Confirmación humana**: quien controla el destino introduce el código en
   `/settings/contacts/{id}/verification/confirm`. Solo un desafío `pending`, no expirado y con
   intentos disponibles puede consumirse. Al acertar pasa a `consumed`.
6. **Evidencia**: `verified_at`, `verified_by`, `verification_method=getchat_code_v1`,
   `verification_evidence` (resultado acotado de `getChat`, hash del código, sin token ni chat
   completo) y `chat_fingerprint = SHA-256(bot_id + ":" + chat_id)`.
7. **Consentimiento separado**: `consent_status=granted` + `consent_at` + identidad declarada.
8. **Vinculación**: `contact_case_links.authorized=true` para cada caso permitido.

Bloqueos de **informe**: sin `verified`, sin consentimiento `granted`, sin vínculo autorizado,
`active=false`, `status=revoked|disabled`, token ausente o manifiesto desactualizado. El bloqueo
ocurre antes de cualquier `sendMessage` de informe.

Estados del desafío: `pending`, `consumed`, `expired`, `locked`. `consumed`, `expired` y `locked` no
se reutilizan.

## Transporte

Interfaz interna `TelegramTransport`:

```text
send_message(chat_id: str, text: str) -> TelegramResult
send_document(chat_id: str, filename: str, content: bytes, caption: str) -> TelegramResult
get_chat(chat_id: str) -> TelegramChat
get_chat_member(chat_id: str, user_id: str) -> TelegramMember
get_me() -> TelegramBot
```

- Implementación real: HTTP con timeout explícito (10 s conexión, 30 s lectura) y sin reintentos
  internos.
- Implementación doble: registra llamadas en memoria o en un archivo temporal de pruebas; nunca toca
  la red.
- La selección se hace por configuración (`SECGUARD_TELEGRAM_TRANSPORT=real|stub`), por defecto
  `stub` en pruebas. Producción exige `real` y token configurado.

## Manifiesto de contenido aprobado

`report-manifest-v1` es la única definición de lo aprobado. Contiene:

```json
{
  "schema_version": "report-manifest-v1",
  "case_id": "...",
  "report_id": "...",
  "report_version_id": "...",
  "report_version_number": 3,
  "dataset_sha256": "...",
  "outbound_text": "...",
  "outbound_text_sha256": "...",
  "pdf_sha256": "...",
  "content_policy": {"include_aliases": true, "allow_ip": false,
                     "allow_internal_names": false, "include_results": false,
                     "include_case_title": false, "detail_level": "executive"},
  "recipients": [{"contact_id": "...", "alias": "...", "chat_fingerprint": "..."}],
  "recipients_sha256": "..."
}
```

- La confirmación manual guarda el manifiesto; la regla automática lo construye al generar el
  informe.
- Antes de enviar, el ejecutor recalcula el manifiesto y compara `manifest_sha256`. Si difiere, no
  llama a Telegram y devuelve `manifest_mismatch`.
- Editar el texto, el PDF, la política o los destinatarios invalida la confirmación manual o exige
  reactivar la regla.
- El manifiesto no contiene token, `chat_id` completo ni contenido privado adicional.

### Revalidación antes de cada componente

El ejecutor compartido, manual y automático, revalida **inmediatamente antes de cada llamada**:

1. destinatario `verified`, `active` y con consentimiento `granted`;
2. vínculo `contact_case_links.authorized=true` para el caso;
3. manifiesto recalculado con `manifest_sha256` coincidente;
4. regla `active`, versión vigente y destinatario incluido, cuando el envío sea automático.

Antes del resumen y de nuevo antes del PDF. Si la revalidación falla entre componentes:

- el componente ya aceptado se conserva y no se reenvía;
- los componentes restantes pasan a `skipped` con `contact_unverified`, `consent_missing`,
  `case_not_authorized`, `manifest_mismatch` o `rule_inactive`;
- el evento queda `partial` si había un componente aceptado, o `skipped` si no había ninguno;
- no se revierte la importación ni se borra la evidencia.

## Contenido del mensaje

- `summary`: texto breve con caso, identificador de versión, snapshot, cifras principales, focos y
  limitaciones; sin IP, nombres internos, Results, filas crudas, CVEs detallados ni enlaces a
  localhost.
- `document`: PDF de la misma versión, nombre `informe-<case_slug>-v<version>.pdf`, con caption que
  identifica el informe.
- El mensaje es comprensible por sí mismo; no depende de abrir la aplicación.
- Orden de envío: primero `summary`, después `document`. Si `summary` falla definitivamente, no se
  envía el documento; si `summary` se acepta y `document` falla, el evento queda `partial`.

## Identidad e idempotencia

```text
idempotency_key = SHA-256(case_id + ":" + report_version_id + ":" + contact_id)
```

- Índice único en `notification_events`. El modo (`manual`/`automatic`) no participa.
- Manual y automático compiten por la misma clave: el segundo reutiliza el evento y no reenvía
  componentes aceptados.
- Evaluación de regla: `Unique(rule_id, import_id)` en `notification_rule_evaluations`.
- La evaluación conserva `generation_key = auto:<evaluation.id>` y `report_version_id`. La creación o
  recuperación de la versión usa `generation_key` con `INSERT ... ON CONFLICT DO NOTHING` y lectura
  posterior. Si el proceso cae antes de guardar el vínculo, el reintento recupera la misma versión;
  si cae después, reutiliza versión y eventos. No se crea una versión nueva para eludir la
  idempotencia.
- Reimportación idéntica: 002 ya impide dos importaciones confirmadas con el mismo hash; además, la
  evaluación no se repite.
- Doble clic/recarga: la clave única y la transacción corta impiden el segundo evento.
- Cruce manual/automático: el segundo reutiliza el evento y registra el cruce en la evidencia.

## Estados y transiciones

Evento: `prepared`, `queued`, `sending`, `accepted`, `partial`, `failed`, `uncertain`, `skipped`.

Componente: `prepared`, `requested`, `accepted`, `failed`, `uncertain`, `skipped`.

| Situación | Evento | Componentes |
|---|---|---|
| Resumen y PDF aceptados | `accepted` | ambos `accepted` |
| Resumen aceptado; PDF falla | `partial` | `summary=accepted`, `document=failed` |
| Resumen falla definitivamente | `failed` | `summary=failed`, `document=skipped` |
| Timeout sin respuesta | `uncertain` | el componente afectado `uncertain` |
| Destinatario inválido antes de llamar | `skipped` | ambos `skipped` |
| Reintento de parcial | `sending` → `accepted`/`failed` | solo `document` recibe nuevo intento |

`accepted` significa «Telegram aceptó la solicitud»; nunca «entregado» ni «leído».

## Reintentos

- Prohibido el reintento automático de un timeout incierto.
- Un fallo definitivo (`4xx` no recuperable, chat inválido, token ausente) puede reintentarse solo por
  acción humana desde la ruta de reintento, y solo para componentes no aceptados.
- Un `5xx` o error de red produce `uncertain`, no `failed`; exige revisión.
- Cada reintento crea un `notification_attempt` nuevo; nunca un evento nuevo.

## Recuperación tras reinicio

- Al arrancar, componentes en `requested` sin `finished_at` pasan a `uncertain` con
  `error_code=interrupted`; no se reintentan automáticamente.
- Una evaluación automática reutiliza la `report_version_id` que generó y los eventos existentes. Si
  el reinicio ocurre antes de crear la versión, puede generarla una vez; si ya existe, no se crea otra.
- Trabajos `claimed` con `claimed_at` vencido (> 120 s) vuelven a `pending` una vez; si vuelven a
  fallar, quedan `failed` y requieren revisión.
- El evento y sus componentes sobreviven al reinicio; la importación confirmada nunca se revierte.

## Taxonomía de errores (códigos seguros)

| Código | Significado | Estado |
|---|---|---|
| `token_missing` | No hay token configurado | `skipped` |
| `chat_not_found` | `getChat` falla o chat inexistente | `skipped` |
| `bot_not_member` | El bot no pertenece al chat | `skipped` |
| `contact_unverified` | Sin verificación vigente | `skipped` |
| `consent_missing` | Sin consentimiento | `skipped` |
| `case_not_authorized` | Sin vínculo al caso | `skipped` |
| `rule_inactive` | Regla desactivada o versión obsoleta | `skipped` |
| `rate_limited` | `429` de Telegram | `failed` (revisión) |
| `invalid_request` | `400` de Telegram | `failed` |
| `forbidden` | `403` de Telegram | `failed` |
| `provider_error` | `5xx` | `uncertain` |
| `timeout` | Sin respuesta | `uncertain` |
| `interrupted` | Reinicio durante el envío | `uncertain` |
| `document_render_failed` | PDF no disponible | `failed` |
| `manifest_mismatch` | El manifiesto recalculado no coincide con el aprobado | `skipped` |
| `code_invalid` | Código de verificación incorrecto | desafío sigue `pending` |
| `code_expired` | Desafío expirado | desafío `expired` |
| `code_consumed` | Desafío ya consumido | sin cambio |
| `verification_locked` | Demasiados intentos o solicitudes | desafío `locked` |
| `component_revalidation_failed` | Cambió destinatario, consentimiento, vínculo, regla o manifiesto antes de un componente | componente `skipped`; evento `partial` o `skipped` |

Nunca se registran token, cabeceras, cuerpo del PDF, texto completo del mensaje ni `chat_id` completo
en logs. La evidencia usa `chat_fingerprint` y `provider_message_id`.

## Evidencia por destinatario

Cada evento registra: informe/versión, snapshot, modo, regla y versión si aplica, `content_policy`,
`content_sha256`, confirmación (manual), estado por componente, fechas, `provider_message_id`,
`attempt_no`, `http_status` y `error_code`. La UI muestra «generado automáticamente, sin revisión
humana individual» cuando corresponde.
