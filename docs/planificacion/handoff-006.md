# Handoff — 006 Informe ejecutivo y notificaciones Telegram

**Fecha**: 2026-11-23  
**Estado**: Cortes A y B implementados y validados localmente. T001–T056 completadas; T057–T081
pendientes. Envío real de Telegram no verificado; reglas automáticas y recuperación automática no
implementadas.  
**Rama**: `006-informe-ejecutivo-telegram`.  
**Constitución**: 1.4.0.

## 1. Artefactos del Corte B

| Archivo / módulo | Contenido |
|---|---|
| `src/secguard_advisor/notifications/contacts.py` | Alta, estado, consentimiento, activación y vínculos por caso |
| `src/secguard_advisor/notifications/verification.py` | Desafío con hash, expiración, intentos y límite de solicitudes |
| `src/secguard_advisor/notifications/channels/base.py` | Protocolo de transporte, resultados y errores tipados |
| `src/secguard_advisor/notifications/channels/telegram.py` | `RealTelegramTransport` (timeouts, sin reintentos) y `StubTelegramTransport` |
| `src/secguard_advisor/notifications/manifest.py` | Manifiesto `report-manifest-v1` y texto saliente |
| `src/secguard_advisor/notifications/confirmations.py` | Confirmación y validación de manifiesto |
| `src/secguard_advisor/notifications/delivery.py` | Eventos, componentes, intentos e idempotencia |
| `src/secguard_advisor/notifications/executor.py` | Revalidación por componente, parciales y recuperación |
| `src/secguard_advisor/notifications/manual.py` | Envío manual síncrono y reintento |
| `src/secguard_advisor/web/routes/contacts.py` | Rutas de contactos, verificación, consentimiento y vínculos |
| `src/secguard_advisor/web/routes/notifications.py` | Preview, confirmación, envío, historial y reintento |
| `src/secguard_advisor/web/templates/contacts/`, `notifications/`, `reports/_notifications.html` | Interfaz del corte |
| `alembic/versions/f3a4b5c6d7e8_add_notifications_manual.py` | Contactos, desafíos, confirmaciones, eventos, componentes, intentos |
| `tests/fixtures/notifications.py` | Helpers con transporte doble y PDF ficticio |
| `tests/unit/test_contacts.py`, `test_contact_verification.py`, `test_telegram_transport.py`, `test_report_manifest.py`, `test_confirmations.py`, `test_manual_send.py`, `test_delivery_*.py`, `test_notifications_manual_migration.py` | Pruebas unitarias del corte |
| `tests/contract/test_contact_verification_routes.py`, `test_manual_delivery.py`, `test_notification_history.py` | Contratos de rutas |
| `tests/acceptance/test_manual_notification_journey.py`, `test_manual_notification_browser.py` | Recorrido y navegador |

El Corte A conserva sus artefactos en `src/secguard_advisor/reports/`, `scripts/` y
`tests/.../test_report_*`.

## 2. Funcionalidad disponible

- **Administración → Contactos y canales**: alta, verificación, consentimiento, activación, vínculos
  por caso, destino enmascarado y estados en español.
- Verificación con código de 6 dígitos, hash persistido, expiración de 10 minutos, 3 intentos y 3
  solicitudes por ventana.
- **Preparar envío manual** desde una versión `ready`: manifiesto, destinatarios y confirmación.
- Envío manual de resumen y PDF con revalidación por componente e idempotencia.
- **Informes y notificaciones**: historial por destinatario, componente e intento, con «Aceptado por
  Telegram» sin equivaler a entrega ni lectura.
- Recuperación al arrancar: solicitudes en vuelo pasan a `uncertain/interrupted`.

## 3. Tareas

- **Completadas**: T001–T056.
- **Pendientes**: T057–T081.
- No se inició T057. Reglas automáticas, envío automático y recuperación automática siguen sin
  implementar.

## 4. Verificación observada

| Comprobación | Resultado |
|---|---|
| `make check` | **822 passed, 41 deselected** |
| Pruebas focalizadas del Corte B | **37 passed** |
| Navegador de contactos/envío + PDF del Corte A | **3 passed** |
| Migración temporal B | upgrade/downgrade OK |
| `pre-commit run --all-files` | Todos los hooks en verde |

## 5. Evidencia

- `docs/evidencia/006-corte-b/README.md`
- `docs/evidencia/006-corte-b/contacts-desktop.png`
- `docs/evidencia/006-corte-b/contacts-mobile.png`
- `docs/evidencia/006-corte-b/manual-preview-desktop.png`
- `docs/evidencia/006-corte-b/manual-history-desktop.png`
- Corte A: `docs/evidencia/006-corte-a/` y `docs/evidencia/006-correcciones-corte-a/`

## 6. Cómo probarlo

1. `uv run alembic upgrade head`.
2. `make dev` (transporte doble por defecto).
3. Crear un caso, confirmar una importación Qualys y generar un informe **ready**.
4. Abrir **Administración → Contactos y canales**, registrar alias y chat ficticio, pedir el código y
   confirmarlo con el valor que registra el transporte doble; otorgar consentimiento, activar y
   vincular al caso.
5. Abrir el informe → **Preparar envío manual** → revisar el manifiesto → **Generar confirmación** →
   **Confirmar y enviar**.
6. Consultar **Informes y notificaciones** para el estado por componente.

Sin `SECGUARD_TELEGRAM_TRANSPORT=real` y sin token, la aplicación usa el transporte doble; no se envían
mensajes reales.

## 7. Decisiones técnicas vigentes

- `notification_events.idempotency_key = SHA-256(case_id:report_version_id:contact_id)`; el modo no
  participa.
- Envío manual síncrono con sesiones cortas; ninguna llamada HTTP con transacción de escritura abierta.
- Solo versiones `ready` se listan, previsualizan o envían; el envío no regenera el informe.
- `report_versions.status` sigue `generating|ready|failed`.
- El token del bot vive solo en `.env`; nunca en SQLite, HTML, capturas, logs ni Git.
- El transporte real tiene timeouts (10 s conexión / 30 s lectura) y no reintenta internamente.

## 8. Límites y pendientes reales

- No se verificó el envío real: no se usó token ni destino reales.
- No se implementaron T057–T081: reglas automáticas, envío automático ni recuperación automática.
- No hubo llamadas pagadas ni evaluación externa.
- La aceptación visual es local (Chrome); no cubre otros navegadores.
- La evaluación semántica humana y el rendimiento formal siguen pendientes.
- 005 conserva sus limitaciones documentadas.

## 9. Siguiente paso

Revisar la evidencia del Corte B y decidir si se autoriza T057. No ejecutar `/speckit.implement`.
