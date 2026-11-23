# Evidencia — Correcciones del Corte B (006)

**Fecha**: 2026-11-23  
**Alcance**: cuatro fallos funcionales del Corte B (T035–T056). No se inició T057 ni el Corte C.  
**Transporte**: exclusivamente `StubTelegramTransport`; datos ficticios y almacenamiento temporal.
No se enviaron códigos ni informes reales, no se consumieron APIs pagadas y no se modificó
`storage/` ni `storage/demo`.

## 1. Fallo 1 — manifiesto y varios destinatarios

**Causa.** La confirmación guardaba el manifiesto del conjunto completo, pero cada evento recibía ese
mismo manifiesto y el ejecutor lo recalculaba con un solo contacto. Los hashes no eran comparables y
todos los eventos quedaban omitidos.

**Corrección.**
- La confirmación conserva el manifiesto del conjunto exacto de destinatarios (`build_manifest`).
- Cada evento guarda un manifiesto derivado de su alcance: mismos campos de contenido, `recipients` de
  un elemento y `approved_recipients_sha256` con el hash del conjunto confirmado.
- El ejecutor compara conjunto contra confirmación y evento individual contra su manifiesto derivado;
  nunca compara alcances distintos.
- La elegibilidad se evalúa por destinatario: la revocación de uno no bloquea a otro que conserva sus
  permisos. Los motivos quedan explícitos (`contact_unverified`, `consent_missing`,
  `case_not_authorized`, `manifest_mismatch`).
- `notification_events.confirmation_id` enlaza el evento con la confirmación que lo aprobó
  (migración `a7b8c9d0e1f2`, aditiva y reversible).

**Comprobación.**
- `tests/unit/test_delivery_scopes.py`: dos destinatarios reciben cada uno un resumen y un PDF;
  manifiesto del evento con un destinatario y hash del conjunto; revocación aislada; cambio de alias
  invalida la confirmación y no envía nada.
- `tests/contract/test_manual_delivery.py::test_manual_delivery_to_two_recipients`.

## 2. Fallo 2 — estados inciertos e idempotencia de ejecución

**Causa.** `send_manual` volvía a ejecutar eventos existentes y `execute_event` solo omitía
componentes `accepted`; un `uncertain` podía reenviarse al repetir el POST. `retry_event` admitía
eventos `partial` con componentes inciertos.

**Corrección.**
- Crear o reutilizar el evento no autoriza la ejecución: `send_manual` solo ejecuta estados `prepared`
  o `queued`.
- Cada componente se reclama con una transición atómica persistida `prepared → requested`
  (`claim_component`) antes de llamar al transporte; dos solicitudes concurrentes no ejecutan el mismo
  componente.
- La resolución del resultado solo aplica si el componente sigue `requested`; un resultado tardío no
  sobreescribe estado más nuevo.
- `retry_event` rechaza con `uncertain_requires_review` si hay un componente `uncertain` o `requested`,
  y solo reencola fallos definitivos (y `skipped` por `summary_failed`); nunca toca `accepted` ni
  `uncertain`. La conciliación explícita no está implementada en el Corte B.
- No hay transacciones SQLite de escritura abiertas durante las llamadas de red.

**Comprobación.**
- Timeout del resumen y repetición del mismo POST: una sola llamada de envío
  (`test_repeated_send_after_timeout_does_not_resend`).
- Resumen aceptado y PDF incierto: el reintento ordinario no vuelve a enviar el PDF
  (`test_accepted_summary_with_uncertain_pdf_is_not_resent_by_retry`).
- Dos ejecuciones concurrentes: una llamada por componente y un intento por componente
  (`test_two_concurrent_executions_claim_each_component_once`) y reclamo atómico entre sesiones
  (`test_claim_component_is_atomic_across_sessions`).
- Resumen aceptado y PDF rechazado definitivamente: se reintenta solo el PDF
  (`test_retry_resends_only_the_failed_document`).
- Reintento con componente en vuelo: rechazado (`test_retry_refuses_while_another_request_is_in_flight`).
- Regresión de rutas: `test_repeated_post_after_tamper_does_not_resend`.

## 3. Fallo 3 — persistencia de intentos de verificación

**Causa.** `confirm_verification` incrementaba intentos y podía bloquear o expirar el desafío, pero la
ruta hacía rollback ante `NotificationError` y borraba esos cambios. Las solicitudes fallidas de código
tampoco contaban para el límite por ventana y el envío se hacía con una transacción de escritura
abierta.

**Corrección.**
- `NotificationError` distingue `persist_state`: los cambios de seguridad se confirman aunque la
  respuesta HTTP sea `422`; solo los fallos sin cambio de estado hacen rollback.
- `start_verification` cuenta y persiste la solicitud antes de la red, no mantiene escritura abierta
  durante `getMe`/`getChat`/`getChatMember`/`sendMessage`, y bloquea el desafío si el envío falla
  (`verification_send_failed`), conservando el conteo.

**Comprobación por HTTP** (`tests/contract/test_contact_verification_routes.py`):
- Cada código incorrecto incrementa el contador persistido (1, 2, 3).
- El tercer error bloquea el desafío (`locked`).
- Una solicitud posterior con el código correcto no lo consume (`consumed_at` nulo; contacto
  `unverified`), incluida una sesión de aplicación nueva.
- El límite de 3 solicitudes por ventana se conserva entre sesiones (la cuarta responde `422`).
- La expiración se conserva y el desafío queda `expired`.

## 4. Fallo 4 — integridad del PDF enviado

**Causa.** El manifiesto usaba el hash del `ReportArtifact`, pero el ejecutor leía el archivo sin
compararlo y lo leía dos veces durante la ejecución.

**Corrección.**
- Antes de iniciar la entrega se lee el PDF una sola vez y se verifica su SHA-256 contra
  `pdf_sha256` del manifiesto confirmado.
- Si falta, ambos componentes pendientes quedan `failed` con `document_render_failed`; si difiere, con
  `pdf_integrity_mismatch`. En ambos casos no se envía el resumen.
- El documento se entrega con los mismos bytes validados y se vuelve a comprobar el hash del búfer
  antes de `send_document`; no hay segunda lectura.
- El hash confirmado nunca se actualiza automáticamente. Los componentes aceptados y su evidencia se
  conservan.

**Comprobación** (`tests/unit/test_delivery_pdf_integrity.py` y contrato):
- PDF alterado: cero llamadas, ambos componentes fallidos con `pdf_integrity_mismatch`; tras restaurar
  el archivo, el reintento envía los bytes correctos.
- PDF alterado durante el envío del resumen: el documento entregado coincide con el hash confirmado y
  el archivo en disco ya no.
- PDF ausente: `document_render_failed` sin envíos.
- El manifiesto persistido conserva el hash aprobado.
- Ruta: `test_tampered_pdf_blocks_the_route_send` muestra el mensaje en el historial.

## 5. Comandos y resultados observados

```bash
uv run pytest tests/unit/test_contacts.py tests/unit/test_contact_verification.py \
  tests/unit/test_telegram_transport.py tests/unit/test_report_manifest.py \
  tests/unit/test_confirmations.py tests/unit/test_manual_send.py \
  tests/unit/test_delivery_states.py tests/unit/test_delivery_idempotency.py \
  tests/unit/test_delivery_recovery.py tests/unit/test_delivery_privacy.py \
  tests/unit/test_delivery_scopes.py tests/unit/test_delivery_execution.py \
  tests/unit/test_delivery_pdf_integrity.py tests/unit/test_notifications_manual_migration.py \
  tests/contract/test_contact_verification_routes.py tests/contract/test_manual_delivery.py \
  tests/contract/test_notification_history.py tests/acceptance/test_manual_notification_journey.py -q
uv run pytest tests/acceptance/test_manual_notification_browser.py -q
uv run pytest tests/acceptance/test_report_browser.py tests/acceptance/test_manual_notification_browser.py \
  tests/integration/test_report_pdf.py -q
make check
uv run pre-commit run --all-files
```

| Comprobación | Resultado |
|---|---|
| Pruebas focalizadas del Corte B | **56 passed** |
| Navegador del Corte B (contactos, integridad, incierto) | **3 passed** |
| Navegador A + navegador B + PDF | **5 passed** |
| `make check` | **842 passed, 43 deselected** |
| `pre-commit run --all-files` | Todos los hooks en verde |
| Migración `a7b8c9d0e1f2` | upgrade/downgrade en almacenamiento temporal |

## 6. Capturas

- `manual-history-integrity-desktop.png`: historial con «El PDF no coincide con el aprobado» y
  «Fallido».
- `manual-history-review-desktop.png`: historial con resumen aceptado, PDF incierto y «Revisión
  requerida; no se reintenta automáticamente» sin botón de reintento.
- `manual-history-review-mobile.png`: el mismo estado en móvil.

## 7. Límites

- Sin envío real de Telegram: no se usó token ni destino reales.
- La conciliación explícita de un resultado incierto no está implementada en el Corte B; el reintento
  ordinario la rechaza.
- No se implementaron reglas automáticas ni T057–T081.
- No se modificaron `storage/` ni `storage/demo`.
