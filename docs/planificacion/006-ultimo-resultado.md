# 006 — Último resultado

**Fecha**: 2026-11-23  
**Estado**: Cortes A y B implementados y validados localmente, con las correcciones del Corte B
(2026-11-23). T001–T056 completadas; T057–T081
pendientes. Envío real de Telegram no verificado; reglas automáticas y recuperación automática no
implementadas.

## 1. Corte A (T001–T034)

- Sección **Informe ejecutivo** con historial de versiones.
- Dataset canónico inmutable por versión, calculado en SQLite y persistido en
  `report_versions.dataset_json`.
- Tarjetas, cuatro gráficas ECharts con tabla alternativa y PDF local de 2–3 páginas.
- Síntesis opcional `report-synthesis-v1` con `claim_refs` y fallback factual.
- Evidencia: `docs/evidencia/006-corte-a/` y `docs/evidencia/006-correcciones-corte-a/`.

## 2. Corte B (T035–T056)

- Contactos en **Administración → Contactos y canales**: alta con alias e identificador de chat, sin
  teléfono ni correo. Estado inicial `unverified`, consentimiento `pending`, `active=false`.
- Verificación por código de 6 dígitos: se persiste solo `code_sha256`, expira en 10 minutos y admite 3
  intentos y 3 solicitudes por ventana; estados `pending`, `consumed`, `expired`, `locked`.
- Consentimiento, activación y vínculo por caso como pasos separados; la activación exige verificación
  y consentimiento.
- Manifiesto `report-manifest-v1` con versión, dataset, texto saliente, hash del PDF, política y
  destinatarios enmascarados.
- Confirmación manual invalidable si cambia el contenido o los destinatarios.
- Eventos, componentes e intentos: idempotencia `SHA-256(caso:versión:contacto)`, componentes
  `summary` y `document` independientes, revalidación por componente, timeout incierto sin reintento
  automático y recuperación al arrancar.
- Historial por destinatario y componente, sin token ni identificadores en claro.
- Transporte real con timeouts y sin reintentos internos; aceptación solo con `StubTelegramTransport`.

## 3. Tareas

**Completadas**: T001–T056 (Setup, Foundational, Corte A y Corte B).

**Pendientes**: T057–T081 (reglas automáticas, envío automático, aceptación integrada y cierre). No se
inició T057.

Migraciones vigentes: `d8e9f0a1b2c3` (A), `e2f3a4b5c6d7` (estado/procedencia) y `f3a4b5c6d7e8`
(Corte B: contactos, desafíos, confirmaciones, eventos, componentes e intentos).

## 4. Verificación observada

| Comprobación | Resultado |
|---|---|
| `make check` | **842 passed, 43 deselected** |
| Pruebas focalizadas del Corte B | **56 passed** |
| Navegador del Corte B (contactos, integridad, incierto) | **3 passed** |
| Navegador A + navegador B + PDF | **5 passed** |
| Migraciones B (`a7b8c9d0e1f2`) upgrade/downgrade | OK |
| `pre-commit run --all-files` | Todos los hooks en verde |

## 4.1 Correcciones del Corte B (2026-11-23)

Cuatro fallos funcionales corregidos sin iniciar el Corte C. Detalle en
`docs/evidencia/006-correcciones-corte-b/`.

1. **Manifiesto y varios destinatarios.** La confirmación conserva el conjunto exacto; cada evento
   guarda un manifiesto derivado de un destinatario con `approved_recipients_sha256`; el ejecutor
   compara alcances equivalentes y la revocación de un destinatario no bloquea a otro.
2. **Estados inciertos e idempotencia.** Crear el evento no autoriza ejecutarlo; cada componente se
   reclama con `prepared → requested` atómico; un POST repetido no reenvía `requested`, `uncertain` ni
   `accepted`; el reintento rechaza componentes inciertos con `uncertain_requires_review`.
3. **Persistencia de verificación.** Los intentos, el bloqueo y la expiración se confirman aunque la
   respuesta sea `422`; las solicitudes fallidas cuentan para el límite; no hay escritura abierta
   durante el envío del código.
4. **Integridad del PDF.** Se lee una sola vez y se verifica contra el manifiesto antes de iniciar; si
   falta o difiere, no se envía el resumen ni el PDF (`document_render_failed` /
   `pdf_integrity_mismatch`); se entregan los mismos bytes validados y el hash confirmado no se
   actualiza.

Migración nueva: `alembic/versions/a7b8c9d0e1f2_add_event_confirmation.py` (`notification_events.confirmation_id`).

## 5. Evidencia

- `docs/evidencia/006-corte-b/README.md`
- `docs/evidencia/006-corte-b/contacts-desktop.png`
- `docs/evidencia/006-corte-b/contacts-mobile.png`
- `docs/evidencia/006-corte-b/manual-preview-desktop.png`
- `docs/evidencia/006-corte-b/manual-history-desktop.png`
- `docs/evidencia/006-correcciones-corte-b/README.md` y capturas de integridad/revisión
- Corte A: `docs/evidencia/006-corte-a/` y `docs/evidencia/006-correcciones-corte-a/`

## 6. Defectos y verificaciones no ejecutadas

**Defectos abiertos de los Cortes A y B**: ninguno observado tras las correcciones del Corte B.

**Verificaciones no ejecutadas**:

- envío real de Telegram con token y destino acordados;
- reglas automáticas y envío automático (Corte C);
- llamadas pagadas y presupuesto;
- evaluación semántica humana;
- rendimiento formal de informe/PDF;
- navegadores distintos de Chrome local.

No son defectos del corte ni aprobaciones.

## 7. Límites

- No se enviaron códigos ni informes reales: toda la aceptación del Corte B usa el transporte doble.
- La conciliación explícita de un resultado incierto no está implementada; el reintento ordinario la
  rechaza.
- «Aceptado por Telegram» significa aceptación del proveedor; no prueba entrega ni lectura.
- Las reglas automáticas, la recuperación automática y el correo no están implementados.
- No se modificaron `storage/` ni `storage/demo`.

## 8. Siguiente paso

Revisar la evidencia de las correcciones del Corte B y decidir si se autoriza el Corte C (T057–T081). No ejecutar
`/speckit.implement`.
