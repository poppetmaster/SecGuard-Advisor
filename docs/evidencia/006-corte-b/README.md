# Evidencia — 006 Corte B: contactos y envío manual

**Fecha**: 2026-11-23  
**Alcance**: T035–T056. Contactos, verificación, consentimiento, vínculo por caso, manifiesto,
confirmación, envío manual y recuperación. No se implementaron reglas automáticas ni Telegram real
verificado.

## 1. Qué se implementó

- Administración → **Contactos y canales** con alias, identificador de chat enmascarado, tipo,
  estado, consentimiento, activación y vínculos por caso.
- Registro inicial `unverified`, `consent_status=pending`, `active=false`.
- Desafío de verificación:
  - código de 6 dígitos enviado mediante el transporte configurado;
  - solo se persiste `code_sha256`;
  - expiración de 10 minutos, máximo 3 intentos y 3 solicitudes por ventana;
  - estados `pending`, `consumed`, `expired`, `locked`;
  - conexión con contacto y `bot_fingerprint`.
- Consentimiento y activación separados. La activación exige verificación y consentimiento.
- Vínculo autorizado por caso.
- Manifiesto `report-manifest-v1` con versión, dataset, texto saliente, hash del PDF, política y
  destinatarios enmascarados.
- Confirmación manual que se invalida si cambia el contenido o los destinatarios.
- Eventos, componentes e intentos con:
  - idempotencia `caso + versión + contacto`, sin el modo;
  - componentes `summary` y `document` independientes;
  - estados preparado, solicitado, aceptado, parcial, fallido, incierto y omitido;
  - revalidación antes de cada componente;
  - timeout incierto sin reintento automático;
  - recuperación de solicitudes en vuelo como `uncertain/interrupted`.
- Historial por destinatario y componente con identificadores enmascarados y sin token.

## 2. Transporte Telegram

- `RealTelegramTransport` implementado con timeout de 10 s de conexión / 30 s de lectura y sin
  reintentos internos.
- `StubTelegramTransport` registra llamadas sin red y permite simular fallo, timeout y rate limit.
- **Transporte real implementado, envío real no verificado**: todas las pruebas de este corte usan el
  transporte doble. No se enviaron códigos ni informes reales.

## 3. Comandos y resultados observados

```bash
uv run pytest tests/unit/test_contacts.py \
  tests/unit/test_contact_verification.py \
  tests/unit/test_telegram_transport.py \
  tests/unit/test_report_manifest.py \
  tests/unit/test_confirmations.py \
  tests/unit/test_manual_send.py \
  tests/unit/test_delivery_states.py \
  tests/unit/test_delivery_idempotency.py \
  tests/unit/test_delivery_recovery.py \
  tests/unit/test_delivery_privacy.py \
  tests/unit/test_notifications_manual_migration.py \
  tests/contract/test_contact_verification_routes.py \
  tests/contract/test_manual_delivery.py \
  tests/contract/test_notification_history.py \
  tests/acceptance/test_manual_notification_journey.py \
  tests/acceptance/test_manual_notification_browser.py -q
make check
uv run pytest tests/acceptance/test_report_browser.py \
  tests/acceptance/test_manual_notification_browser.py \
  tests/integration/test_report_pdf.py -q
uv run pre-commit run --all-files
```

| Comprobación | Resultado |
|---|---|
| Pruebas focalizadas del Corte B | **37 passed** |
| `make check` | **822 passed, 41 deselected** |
| Navegador de contactos/envío + PDF del Corte A | **3 passed** |
| Migración temporal B | upgrade/downgrade OK |
| `pre-commit` | Todos los hooks en verde |

La migración del Corte B es
`alembic/versions/f3a4b5c6d7e8_add_notifications_manual.py`; añade contactos, desafíos,
confirmaciones, eventos, componentes e intentos.

## 4. Capturas

- `contacts-desktop.png`: administración de contactos con destino enmascarado.
- `contacts-mobile.png`: contactos en móvil.
- `manual-preview-desktop.png`: destinatarios, confirmación y manifiesto exacto.
- `manual-history-desktop.png`: historial por destinatario y componente.

## 5. Cómo probarlo

1. `uv run alembic upgrade head`.
2. `make dev`.
3. Abrir **Administración → Contactos y canales**, registrar alias y chat ficticio.
4. Enviar el código y confirmarlo con el valor que registra el transporte doble.
5. Otorgar consentimiento, activar y vincular el contacto al caso.
6. Abrir un informe **ready** → **Preparar envío manual**.
7. Revisar el manifiesto, generar la confirmación y pulsar **Confirmar y enviar**.
8. Consultar **Informes y notificaciones** para ver estados por componente.

Sin `SECGUARD_TELEGRAM_TRANSPORT=real` y sin token, la aplicación usa el transporte doble. No se
envían mensajes reales en esta aceptación.

## 5.1 Correcciones posteriores (2026-11-23)

Cuatro fallos funcionales de este corte se corrigieron después: manifiesto por alcance para varios
destinatarios, ejecución atómica e idempotente de componentes, persistencia de intentos de verificación
e integridad del PDF. Los resultados de la tabla anterior corresponden al corte original; la evidencia
vigente está en `docs/evidencia/006-correcciones-corte-b/`.

## 6. Límites

- No se verificó el envío real: no se usó un token real ni un destino acordado.
- La verificación semántica de citas y la aceptación real de Telegram quedan pendientes.
- No se implementaron reglas automáticas, T057 ni Telegram fuera del envío manual.
- No se modificaron `storage/` ni `storage/demo`.
- Los estados `accepted` significan aceptación del proveedor; no entrega ni lectura.
