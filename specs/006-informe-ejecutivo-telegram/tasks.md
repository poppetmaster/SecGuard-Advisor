# Tasks: 006 — Informe ejecutivo visual y notificaciones mediante Telegram

**Input**: `specs/006-informe-ejecutivo-telegram/` — constitución 1.4.0, `AGENTS.md`, `spec.md`,
`plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md` y `docs/planificacion/handoff-006.md`.

**Prerequisites**: `plan.md`, `spec.md`, `data-model.md`, `contracts/` y `research.md`.

**Tests**: sí. La especificación y la instrucción exigen pruebas de métricas, aislamiento,
confirmación invalidada, doble envío, timeout incierto, reinicio, PDF y navegador. Las pruebas se
escriben antes de la implementación cuando la tarea lo indique y deben fallar primero.

**Organización**: tres cortes funcionales independientes:

- **Corte A**: informe ejecutivo web y PDF.
- **Corte B**: contactos y envío manual, incluidos eventos, componentes, intentos y ejecutor.
- **Corte C**: reglas automáticas y aceptación integrada, reutilizando la entrega de B.

**Límites**: no se ejecutan llamadas pagadas, envíos reales, migraciones ni instalaciones durante este
paso. Todos los mensajes usan `SECGUARD_TELEGRAM_TRANSPORT=stub` y datos ficticios. No se introduce
P1–P4 ni se retoma 003.

## Formato

`- [ ] TNNN [P?] [USn] Descripción con archivo(s)`
`  - Depende de: ...`
`  - Comprobación: ...`
`  - Evidencia: ...`

`[P]` solo cuando el archivo no colisiona y no depende de una tarea incompleta. `[USn]` mapea a
`spec.md`: US1 informe, US2 contactos/manual, US3 regla automática, US4 auditoría.

---

## Phase 1: Setup (infraestructura compartida)

**Propósito**: preparar herramientas, configuración y esqueletos sin implementar comportamiento.

- [X] T001 [P] Verificar baseline y toolchain en `pyproject.toml`, `package.json`, `uv.lock` y `Makefile`.
  - Depende de: ninguna.
  - Comprobación: `uv sync --locked` resuelve; `node --version` está en el rango `>=26.11.1 <27`; `make check` pasa antes de tocar 006.
  - Evidencia: salida de `uv sync --locked`, `node --version`, `npm --version` y `make check` con fecha.

- [X] T002 [P] Añadir `playwright` a `pyproject.toml` y crear `scripts/check_pdf_runtime.py`.
  - Depende de: T001.
  - Comprobación: el script lanza Chrome con `channel="chrome"` y, si no existe, informa que se requiere Chromium empaquetado; no genera PDF todavía.
  - Evidencia: salida del script con navegador detectado o mensaje de bloqueo; ausencia de instalación en este paso.

- [X] T003 [P] Añadir configuración de Telegram y almacenamiento de informes en `src/secguard_advisor/config.py`.
  - Depende de: T001.
  - Comprobación: `telegram_bot_token: SecretStr | None` lee `TELEGRAM_BOT_TOKEN`; `telegram_transport` acepta `stub|real` con defecto `stub`; `reports_dir` deriva de `storage_dir`; ningún valor secreto tiene defecto real.
  - Evidencia: pruebas unitarias de configuración y ejemplo de `.env` documentado en `README.md`.

- [X] T004 [P] Crear esqueletos de paquetes en `src/secguard_advisor/reports/__init__.py`, `src/secguard_advisor/notifications/__init__.py` y `src/secguard_advisor/notifications/channels/__init__.py`.
  - Depende de: T001.
  - Comprobación: `uv run python -c "import secguard_advisor.reports, secguard_advisor.notifications"` funciona; `ruff check` sin errores.
  - Evidencia: import exitoso y salida de Ruff.

- [X] T005 [P] Registrar fixtures y markers compartidos en `tests/conftest.py` y `tests/fixtures/__init__.py`.
  - Depende de: T001.
  - Comprobación: los nuevos tests pueden importar fixtures sin duplicar bases; no se alteran fixtures existentes.
  - Evidencia: `uv run pytest --collect-only -q` sin errores de importación.

- [X] T006 Documentar prerrequisitos de renderizado local en `README.md` y `AGENTS.md`.
  - Depende de: T002.
  - Comprobación: se declara que Node participa en las gráficas del PDF (ECharts SSR), que Playwright/Chrome genera el PDF y que ambos son requisitos del Corte A.
  - Evidencia: secciones enlazadas y revisadas; sin afirmar que ya están implementados.

---

## Phase 2: Foundational (prerrequisitos bloqueantes)

**Propósito**: utilidades comunes que usan A, B y C. No incluye tablas de un corte posterior.

- [X] T007 [P] Implementar JSON canónico y hash en `src/secguard_advisor/reports/canonical.py`.
  - Depende de: T004.
  - Comprobación: `canonical_json()` usa `sort_keys=True`, separadores `(",", ":")`, UTF-8 y sin espacios; `sha256_hex()` devuelve 64 hex; dos dicts equivalentes producen el mismo hash.
  - Evidencia: T007 implementa y crea `tests/unit/test_canonical_json.py` con orden, Unicode, dict anidado y hash estable.

- [X] T008 [P] Crear fixtures ficticias en `tests/fixtures/report_fixtures.py`.
  - Depende de: T005.
  - Comprobación: incluye un caso ficticio con snapshot confirmado, severidades 1–5, `pending_known`, `fixed`, `manual_review`, indicadores positivos/negativos/indeterminados, un registro con varios CVE, dos activos sin identificación y un activo con FQDN/DNS/NetBIOS/IP.
  - Evidencia: fixtures importables y usadas por al menos un test de A y uno de B.

- [X] T009 [P] Implementar política de contenido y alias en `src/secguard_advisor/reports/privacy.py`.
  - Depende de: T004.
  - Comprobación: la política por defecto es `include_aliases=true`, `allow_ip=false`, `allow_internal_names=false`, `include_results=false`, `include_case_title=false`, `detail_level="executive"`; los alias son deterministas `Activo 01..N`; el contenido saliente nunca incluye etiqueta interna, IP, DNS, NetBIOS, FQDN ni Results.
  - Evidencia: cubierto por T032 (`test_report_privacy.py`); T009 no crea el archivo.

- [X] T010 [P] Crear códigos de error estables en `src/secguard_advisor/reports/errors.py` y `src/secguard_advisor/notifications/errors.py`.
  - Depende de: T004.
  - Comprobación: existen `manifest_mismatch`, `verification_locked`, `code_invalid`, `code_expired`, `code_consumed`, `contact_unverified`, `consent_missing`, `case_not_authorized`, `rule_inactive`, `rate_limited`, `timeout`, `interrupted`, `document_render_failed`; no incluyen secretos.
  - Evidencia: T010 implementa y crea `tests/unit/test_error_codes.py`, que enumera los códigos y verifica que no hay token/chat.

- [X] T011 Extender `tests/fixtures/report_fixtures.py` con un constructor de snapshot confirmado reutilizable por A/B/C.
  - Depende de: T008.
  - Comprobación: el constructor crea `QualysImport` confirmado y filas coherentes con `severity_level BETWEEN 1 AND 5`, `status_group IN ('pending_known','fixed','manual_review')` y `exploitability_eval`/`malware_eval` válidos.
  - Evidencia: test que consulta el snapshot y verifica conteos base.

**Checkpoint**: utilidades, fixtures y configuración listas; ningún corte depende de tablas futuras.

---

## Phase 3: Corte A — Informe ejecutivo web y PDF (US1, P1) 🎯 MVP

**Goal**: generar un informe verificable desde un snapshot confirmado, con dataset inmutable, tarjetas,
gráficas, web interactiva y PDF local de 2–3 páginas.

**Independent Test**: con el snapshot ficticio confirmado, generar un informe, comparar cada cifra con
SQLite, abrir la vista web, descargar el PDF y verificar misma instantánea, filtros, cifras y títulos.

### Migración y datos

- [X] T012 [US1] Crear la migración `alembic/versions/<rev>_add_reports.py` y actualizar `src/secguard_advisor/db/models.py`.
  - Depende de: T004.
  - Comprobación: crea `reports`, `report_versions` (con `generation_key` String(64) nullable e índice único parcial cuando no es nulo), `report_artifacts`; `report_versions` exige `version_number >= 1` y `Unique(report_id, version_number)`; `report_artifacts` exige `kind IN ('pdf','chart_svg')` y `Unique(report_version_id, kind, chart_key)`; extiende `runs` con `kind='report'`, `conversation_id` nullable, outcomes `report_ready|report_factual` e índice activo limitado a `kind='chat'`. No referencia tablas de C. `uv run alembic upgrade head` y `downgrade -1` funcionan en una base temporal.
  - Evidencia: revisión Alembic, `alembic upgrade head`, `alembic downgrade -1`, `alembic upgrade head`; T012 implementa y crea `tests/unit/test_reports_migration.py`, que cubre `generation_key` único nullable.

- [X] T013 [P] [US1] Definir el esquema y constructor del dataset en `src/secguard_advisor/reports/dataset.py`.
  - Depende de: T007, T012.
  - Comprobación: produce `report-dataset-v1` con `case`, `snapshot`, `filters`, `base`, `cards`, `severity`, `assets_top`, `exploitability`, `malware`, `coverage`, `limitations` y `metric_versions`; `dataset_sha256` estable; rechaza snapshot no confirmado o de otro caso.
  - Evidencia: cubierto por T028 (`test_report_dataset.py`); T013 no crea el archivo.

- [X] T014 [US1] Implementar métricas deterministas en `src/secguard_advisor/reports/metrics.py`.
  - Depende de: T011, T013.
  - Comprobación: `COUNT(*)` sobre filas; sin `COUNT(DISTINCT cve)` ni `JOIN` a CVEs en agregados; `manual_review` es unión contada una vez; `exploitability` y `malware` son independientes; cada tarjeta y gráfica declara `scope` y `denominator`; `fixed` se muestra aparte.
  - Evidencia: cubierto por T027 (`test_report_metrics.py`); T014 no crea el archivo.

- [X] T015 [US1] Implementar top 5 de activos y recorte en `src/secguard_advisor/reports/aliasing.py`.
  - Depende de: T009, T014.
  - Comprobación: top 5 por críticos desc, altos desc, total desc, etiqueta asc; declara `total_assets`, `assets_with_critical_or_high`, `recorted` y «Otros»; alias deterministas; la etiqueta interna no entra al contenido saliente.
  - Evidencia: T015 implementa y crea `tests/unit/test_report_aliasing.py` con empate, menos de 5, más de 5 y `Sin activo`.

- [X] T016 [US1] Construir opciones ECharts y conclusiones en `src/secguard_advisor/reports/charts.py`.
  - Depende de: T014, T015.
  - Comprobación: cuatro gráficas (`severity`, `assets`, `exploitability`, `malware`); títulos-conclusión deterministas; severidad 1–5; dos series pendientes/fixed con denominadores separados; sin 3D; opciones serializables sin funciones.
  - Evidencia: T016 implementa y crea `tests/unit/test_report_charts.py` con opciones y conclusiones.

### Renderizado

- [X] T017 [US1] Implementar `scripts/render_report_charts.mjs` y actualizar `package.json`.
  - Depende de: T016.
  - Comprobación: `node scripts/render_report_charts.mjs --check` sale 0; renderiza cada opción con `renderer:"svg", ssr:true`; produce SVG con dimensiones y texto; falla con código distinto de 0 si una opción es inválida.
  - Evidencia: SVG generados en `tmp_path`, salida de `--check` y validación del SVG embebido en T030.

- [X] T018 [US1] Implementar artefactos atómicos en `src/secguard_advisor/reports/artifacts.py`.
  - Depende de: T012.
  - Comprobación: ruta `storage/reports/<case_id>/<report_id>/<version>/`; escritura temporal + `os.replace`; calcula SHA-256 y bytes; nunca sobrescribe un artefacto existente; una versión nueva usa otra carpeta.
  - Evidencia: T018 implementa y crea `tests/unit/test_report_artifacts.py` con escritura, colisión y hash.

- [X] T019 [US1] Crear plantilla de impresión con CSS `@page` inline en `src/secguard_advisor/web/templates/reports/print.html`.
  - Depende de: T016.
  - Comprobación: A4, márgenes, tipografía ≥10 pt, `break-inside: avoid` en tarjetas/gráficas, sin enlaces a localhost, sin depender de la pantalla; incluye identificador, snapshot, filtros, tarjetas, gráficas, focos, recomendaciones y limitaciones.
  - Evidencia: HTML de impresión renderizado con Jinja y revisión de CSS; cubierto visualmente por T029/T031.

- [X] T020 [US1] Implementar el renderizador PDF en `src/secguard_advisor/reports/render.py`.
  - Depende de: T002, T017, T018, T019.
  - Comprobación: Playwright lanza Chrome/Chromium, `page.pdf(format="A4", print_background=True)` produce 2–3 páginas; si el navegador no está disponible devuelve error controlado y no crea artefacto parcial; no usa CDN ni servicios externos.
  - Evidencia: cubierto por T030 (`test_report_pdf.py`); T020 no crea el archivo.

### Síntesis y servicio

- [X] T021 [P] [US1] Implementar esquema y servicio de síntesis en `src/secguard_advisor/reports/synthesis.py`.
  - Depende de: T007, T012.
  - Comprobación: implementa `report-synthesis-v1` según `contracts/report-synthesis.md`; `summary`, `focus`, `recommendations` y `limitations`; cada recomendación declara `basis IN ('csv_fact','documentary','agent_proposal')`, `claim_refs` y `evidence_refs`; las cifras se renderizan desde el dataset y los números libres se rechazan; permite identificadores QID/CVE/versión/fecha; `documentary` exige cita existente y aceptada, sin afirmar respaldo semántico; una recomendación sin respaldo comprobado se muestra como propuesta; usa `Run(kind='report')`, `ai_config`, autorización por caso, presupuesto y `ai_requests`; si falla o no hay presupuesto devuelve fallback factual sin llamada.
  - Evidencia: T021 implementa y crea `tests/unit/test_report_synthesis.py` (válida, número libre, identificador, conteo sin denominador, cita ausente, cita sin respaldo semántico, sin presupuesto y proveedor no autorizado). T071 amplía el caso automático.

- [X] T022 [US1] Implementar ciclo de vida de informe y versiones en `src/secguard_advisor/reports/service.py`.
  - Depende de: T013, T014, T016, T018, T020, T021.
  - Comprobación: solo genera desde snapshot confirmado; crea `report_version` inmutable con dataset, charts, PDF y SVG; regenerar crea otra versión; una importación posterior no cambia versiones históricas; el PDF se asocia a la versión.
  - Evidencia: cubierto por T028 (`test_report_service.py`); T022 no crea el archivo.

### Rutas y UI

- [X] T023 [US1] Crear rutas en `src/secguard_advisor/web/routes/reports.py` e incluirlas en `src/secguard_advisor/web/app.py`.
  - Depende de: T022.
  - Comprobación: `GET /cases/{case_id}/reports`, `GET .../new`, `POST .../reports`, `GET .../versions/{version}`, `GET .../pdf`, `GET .../preview`; 404 fuera del caso; 409 si el PDF no está listo; 422 con snapshot inválido; un `GET` nunca genera ni envía.
  - Evidencia: T023 implementa y crea `tests/contract/test_report_routes.py`.

- [X] T024 [P] [US1] Crear plantillas `src/secguard_advisor/web/templates/reports/view.html`, `_cards.html`, `_charts.html` y `_history.html`.
  - Depende de: T023.
  - Comprobación: tarjetas con definición y denominador; gráficas con título, unidades, tooltips y tabla alternativa; historial con versión, snapshot, autor y estado de síntesis; responsive; rótulo «Sin síntesis de IA» cuando aplica.
  - Evidencia: cubierto por T029/T031 con snapshot ficticio y capturas.

- [X] T025 [P] [US1] Implementar gráficas interactivas en `src/secguard_advisor/web/static/js/report-charts.js` y actualizar `src/secguard_advisor/web/templates/base.html`.
  - Depende de: T016.
  - Comprobación: usa `window.echarts.init` con canvas; lee `data-chart-data`; no usa CDN; conserva exportación PNG si aplica; degrada a tabla si ECharts no carga.
  - Evidencia: cubierto por T031 (navegador y consola).

- [X] T026 [P] [US1] Añadir navegación «Informe ejecutivo» en `src/secguard_advisor/web/templates/components/navigation.html` y `src/secguard_advisor/web/navigation.py`.
  - Depende de: T023.
  - Comprobación: la entrada aparece en escritorio y móvil; marca la sección activa; no rompe enlaces existentes.
  - Evidencia: cubierto por T031/T073 (captura y navegación).

### Pruebas del Corte A

- [X] T027 [P] [US1] Escribir `tests/unit/test_report_metrics.py`.
  - Depende de: T014.
  - Comprobación: cubre denominadores, multi-CVE sin multiplicación, `manual_review` una vez, indicadores independientes, `fixed` separado, `Sin activo`, severidad 1–5 y filtros.
  - Evidencia: salida de pytest y nombres de casos.

- [X] T028 [P] [US1] Escribir `tests/unit/test_report_dataset.py` y `tests/unit/test_report_service.py`; T028 es dueña de ambos y T013/T022 no los crean.
  - Depende de: T013, T022.
  - Comprobación: hash canónico estable; snapshot no confirmado/ajeno rechazado; dos versiones inmutables; historial intacto tras importar otro CSV.
  - Evidencia: salida de pytest y `dataset_sha256` de ambas versiones.

- [X] T029 [P] [US1] Escribir `tests/contract/test_report_concordance.py`.
  - Depende de: T022, T023, T024.
  - Comprobación: cada valor de tarjeta/gráfica coincide con SQLite, HTML y tabla alternativa; el PDF contiene los mismos identificadores y títulos; 100 % de concordancia.
  - Evidencia: pytest y diff de valores por tarjeta/gráfica.

- [X] T030 [P] [US1] Escribir `tests/integration/test_report_pdf.py` para comprobaciones automáticas del PDF con pypdf.
  - Depende de: T020.
  - Comprobación: 2–3 páginas A4; extracción de texto por página sin páginas vacías; presencia de objetos embebidos de las gráficas; identificador, snapshot, filtros y títulos extraíbles; sin enlaces a localhost. NO se atribuyen a pypdf recortes, espacios ni legibilidad visual.
  - Evidencia: pytest, metadatos de páginas y PDF de muestra en `docs/evidencia/006-corte-a/`; la inspección visual queda en T031.

- [X] T031 [US1] Probar navegador y revisar visualmente el PDF en `tests/acceptance/test_report_browser.py` y `docs/evidencia/006-corte-a/`.
  - Depende de: T024, T025, T026, T030.
  - Comprobación: (a) Playwright abre escritorio y móvil; tarjetas visibles; tooltips/tablas funcionan; sin errores de consola; navegación correcta. (b) Inspección visual del PDF renderizado: abrir las páginas como imágenes con el visor local o la herramienta disponible; verificar gráficas completas, sin cortes, espacios, solapamientos, páginas vacías o texto ilegible; registrar capturas y notas. No exige firma ni aprobación humana adicional. La inspección visual se registra como evidencia; no se automatiza con pypdf.
  - Evidencia: capturas desktop/móvil, capturas/notas de las páginas del PDF y salida de pytest.

- [X] T032 [P] [US1] Escribir `tests/unit/test_report_privacy.py` y `tests/contract/test_report_isolation.py`; T032 es dueña de ambos y T009 no crea el archivo.
  - Depende de: T009, T022, T023.
  - Comprobación: PDF y contenido saliente sin IP/nombres internos/Results/título sensible; alias y «Otros»; un informe de otro caso devuelve 404; no hay cruce de datasets.
  - Evidencia: pytest y búsqueda de cadenas prohibidas en el PDF.

- [X] T033 [US1] Escribir `tests/acceptance/test_report_journey.py`.
  - Depende de: T023, T024, T025, T026, T027–T032.
  - Comprobación: recorrido completo con snapshot ficticio: generar, revisar, descargar PDF, verificar concordancia y cero envíos.
  - Evidencia: pytest y artefactos de la ejecución.

- [X] T034 [US1] Documentar el Corte A en `docs/evidencia/006-corte-a/README.md` y actualizar `docs/planificacion/006-ultimo-resultado.md`.
  - Depende de: T033.
  - Comprobación: incluye comandos, resultados, capturas, limitaciones (Node/Playwright), top 5, factual/síntesis y pendientes.
  - Evidencia: documento revisado y enlaces a PDF/capturas.

## Correcciones posteriores a la revisión del Corte A (2026-11-23)

Estas correcciones pertenecen a T001–T034 y no habilitan T035.

- [X] C01 Integrar la síntesis con autorización por alcance, procedencia real (`private_qualys` /
      `synthetic_public`), presupuesto con reserva/liquidación, contexto y concurrencia de 005.
- [X] C02 Validar todos los textos, rechazar contradicciones de ausencia, cifras libres, IP/nombres
      internos y citas inexistentes; resumen y focos deterministas.
- [X] C03 Separar generación en transacciones cortas, usar `report_versions.status`, área temporal,
      publicación solo de versiones `ready` y limpieza acotada.
- [X] C04 Mantener `generation_key` idempotente y ligado al caso; cubrir concurrencia y reintento.
- [X] C05 Añadir regresiones de autorización, presupuesto, consumo, contexto, inicialización,
      contradicción, limitaciones, citas, fallo parcial de archivos y concurrencia.
- [X] C06 Ejecutar `make check`, PDF/navegador y documentar la evidencia en
      `docs/evidencia/006-correcciones-corte-a/`.

**Verificado**: `pre-commit` final en verde. Las integraciones no ejecutadas se limitan a envío real y proveedores pagados, fuera del Corte A.

**Checkpoint A**: informe web/PDF verificable, inmutable y sin envíos.

---

## Phase 4: Corte B — Contactos y envío manual (US2, P2; auditoría US4)

**Goal**: administrar contactos, verificar el destino, registrar consentimiento y vínculo, confirmar
manualmente y ejecutar envíos con eventos, componentes e intentos independientes.

**Independent Test**: con el transporte doble, solicitar el código a un contacto no verificado aunque
el informe esté bloqueado, verificar, consentir, vincular, confirmar y enviar; comprobar estados y
evitar duplicados.

### Migración y servicios base

- [ ] T035 [US2] Crear la migración `alembic/versions/<rev>_add_notifications_manual.py` y actualizar `src/secguard_advisor/db/models.py`.
  - Depende de: T012.
  - Comprobación: crea `contact_channels`, `contact_case_links`, `contact_verification_challenges`, `report_confirmations`, `notification_events`, `notification_components` y `notification_attempts`; incluye `Unique(channel, chat_id)`, `Unique(event_id, kind)`, `Unique(event_id, component_kind, attempt_no)`, `idempotency_key` único, `Check(status IN ('pending','consumed','expired','locked'))` en el desafío y `Check(status != 'consumed' OR consumed_at IS NOT NULL)`; no crea tablas de reglas. `upgrade head`/`downgrade -1` en base temporal.
  - Evidencia: revisión Alembic, `alembic upgrade/downgrade`; T035 implementa y crea `tests/unit/test_notifications_manual_migration.py` con la restricción del desafío.

- [ ] T036 [P] [US2] Implementar contactos, consentimiento y vínculos en `src/secguard_advisor/notifications/contacts.py`.
  - Depende de: T035.
  - Comprobación: alta `unverified`, `consent_status=pending`, `active=false`; `status IN ('unverified','verified','revoked','disabled')`; `consent_status IN ('pending','granted','revoked')`; vínculo `authorized` por caso; revocar bloquea informes; no solicita teléfono ni correo.
  - Evidencia: `tests/unit/test_contacts.py` con alta, duplicado, consentimiento y vínculo.

- [ ] T037 [US2] Implementar desafíos de verificación en `src/secguard_advisor/notifications/verification.py`.
  - Depende de: T035, T036.
  - Comprobación: crea `contact_verification_challenges` con `code_sha256`, `bot_fingerprint`, `purpose='contact_verification'`, `expires_at` +10 min, `attempts`, `max_attempts=3`, `request_count`, `window_started_at`; máximo 3 solicitudes por ventana; consume solo `pending` no expirado; estados `pending|consumed|expired|locked`; nunca guarda código en claro ni token.
  - Evidencia: cubierto por T049 (`test_contact_verification.py`); T037 no crea el archivo.

- [ ] T038 [P] [US2] Implementar transporte Telegram real/doble en `src/secguard_advisor/notifications/channels/base.py` y `src/secguard_advisor/notifications/channels/telegram.py`.
  - Depende de: T003, T010.
  - Comprobación: `send_message`, `send_document`, `get_chat`, `get_chat_member`, `get_me`; timeout 10/30 s; sin reintentos internos; `stub` registra llamadas sin red; `real` exige token; errores mapeados a códigos seguros; no registra token/chat completo.
  - Evidencia: T038 implementa y crea `tests/unit/test_telegram_transport.py` con doble y errores simulados.

- [ ] T039 [P] [US2] Implementar el manifiesto canónico en `src/secguard_advisor/notifications/manifest.py`.
  - Depende de: T007, T035.
  - Comprobación: `report-manifest-v1` incluye caso, informe, versión, `dataset_sha256`, `outbound_text`, `outbound_text_sha256`, `pdf_sha256`, `content_policy`, `recipients` y `recipients_sha256`; `manifest_sha256` estable; no incluye token ni chat completo.
  - Evidencia: cubierto por T050 (`test_report_manifest.py`); T039 no crea el archivo.

### Entrega y ejecución manual

- [ ] T040 [US2] Implementar eventos, componentes, intentos e idempotencia en `src/secguard_advisor/notifications/delivery.py`.
  - Depende de: T035, T038, T039.
  - Comprobación: `idempotency_key = SHA-256(case_id + ':' + report_version_id + ':' + contact_id)` única; el modo no participa; componentes `summary`/`document` con estado independiente; un componente `accepted` no vuelve a `requested`; `prepared|queued|sending|accepted|partial|failed|uncertain|skipped`; guarda manifiesto ejecutado.
  - Evidencia: T040 implementa y crea `tests/unit/test_delivery_states.py`; la idempotencia queda en T051 (`test_delivery_idempotency.py`).

- [ ] T041 [US2] Implementar el ejecutor manual compartido y su recuperación en `src/secguard_advisor/notifications/executor.py`.
  - Depende de: T040.
  - Comprobación: reclama en transacción corta (`BEGIN IMMEDIATE`) y llama a Telegram fuera de transacción; **antes de cada componente** (resumen y PDF) revalida destinatario verificado, consentimiento, vínculo y manifiesto; si se revoca, conserva el componente aceptado y marca los restantes `skipped`; al arrancar, componentes `requested` sin resultado pasan a `uncertain/interrupted`; no reintenta automáticamente; reintento manual solo de componentes no aceptados; un fallo no revierte la importación.
  - Evidencia: cubierto por T052 (`test_delivery_recovery.py`), que incluye revocación entre resumen y PDF.

- [ ] T042 [US2] Implementar confirmación y manifiesto en `src/secguard_advisor/notifications/confirmations.py`.
  - Depende de: T039, T040.
  - Comprobación: confirma versión, destinatarios, texto, PDF y política; guarda `manifest_json`/`manifest_sha256`; invalida si cambia el informe, PDF, política o destinatarios; no confirma contactos no verificados, sin consentimiento, inactivos o no vinculados.
  - Evidencia: cubierto por T050 (`test_confirmations.py`); T042 no crea el archivo.

- [ ] T043 [US2] Implementar el envío manual en `src/secguard_advisor/notifications/manual.py`.
  - Depende de: T041, T042.
  - Comprobación: recalcula manifiesto; si `manifest_sha256` no coincide devuelve `manifest_mismatch` y no llama; crea/reutiliza evento por contacto; encola resumen y PDF; un doble clic devuelve el evento existente.
  - Evidencia: cubierto por T051 (`test_manual_send.py`); T043 no crea el archivo.

### Rutas y UI

- [ ] T044 [US2] Crear rutas de contactos en `src/secguard_advisor/web/routes/contacts.py` e incluirlas en `src/secguard_advisor/web/app.py`.
  - Depende de: T036, T037, T038.
  - Comprobación: `GET/POST /settings/contacts`, `POST .../verification`, `POST .../verification/confirm`, `POST .../consent`, `POST .../status`, `POST /cases/{case_id}/contacts/{contact_id}`; el código se envía con `unverified` y sin consentimiento/vínculo; no muestra token ni chat completo.
  - Evidencia: cubierto por T049 (`test_contact_verification_routes.py`); T044 no crea el archivo.

- [ ] T045 [US2] Crear rutas de confirmación y notificaciones en `src/secguard_advisor/web/routes/notifications.py` e incluirlas en `src/secguard_advisor/web/app.py`.
  - Depende de: T041, T042, T043.
  - Comprobación: confirmaciones, envío manual, historial y reintento; 409 `manifest_mismatch`; 422 contacto inválido; 202 eventos; un GET no envía.
  - Evidencia: cubierto por T053 (`test_manual_delivery.py`) y T054 (`test_notification_history.py`); T045 no crea los archivos.

- [ ] T046 [P] [US2] Crear plantillas de contactos en `src/secguard_advisor/web/templates/contacts/index.html`, `_form.html` y `_verification.html`.
  - Depende de: T044.
  - Comprobación: alias, tipo, estado, consentimiento, casos autorizados y última verificación; formulario de código; mensajes de error claros; sin token ni chat completo; responsive.
  - Evidencia: cubierto por T049/T055 (captura y recorrido).

- [ ] T047 [P] [US2] Crear plantillas de informes/notificaciones en `src/secguard_advisor/web/templates/notifications/_panel.html`, `_preview.html`, `_history.html` y `src/secguard_advisor/web/templates/reports/_notifications.html`.
  - Depende de: T045.
  - Comprobación: vista previa del contenido exacto; confirmación; destinatarios; estados por componente; historial con modo, regla, fechas e identificador; «preparado/solicitado/aceptado/parcial/fallido/incierto».
  - Evidencia: cubierto por T054/T055 (captura y contrato).

- [ ] T048 [P] [US2] Añadir navegación de contactos y notificaciones en `src/secguard_advisor/web/templates/components/navigation.html` y `src/secguard_advisor/web/navigation.py`.
  - Depende de: T044, T045.
  - Comprobación: Administración → Contactos; caso → Informes y notificaciones; escritorio y móvil; sección activa.
  - Evidencia: cubierto por T031/T055/T073.

### Pruebas del Corte B

- [ ] T049 [P] [US2] Escribir `tests/unit/test_contact_verification.py` y `tests/contract/test_contact_verification_routes.py`; T049 es dueña de ambos y T037/T044 no los crean.
  - Depende de: T037, T044.
  - Comprobación: el código se envía con informe bloqueado; hash/expiración/intentos/consumo/límites; no se guarda código en claro ni token; sin código correcto no hay `verified`.
  - Evidencia: pytest y consulta a `contact_verification_challenges`.

- [ ] T050 [P] [US2] Escribir `tests/unit/test_report_manifest.py` y `tests/unit/test_confirmations.py`; T050 es dueña de ambos y T039/T042 no los crean.
  - Depende de: T039, T042.
  - Comprobación: manifiesto canónico; cambio de texto/PDF/política/destinatarios invalida; confirmación válida solo con manifiesto coincidente.
  - Evidencia: pytest con manifiestos alterados.

- [ ] T051 [P] [US2] Escribir `tests/unit/test_manual_send.py` y `tests/unit/test_delivery_idempotency.py`; T051 es dueña de ambos y T040/T043 no los crean.
  - Depende de: T040, T043.
  - Comprobación: doble clic/recarga no crea segundo evento; un componente aceptado no se reenvía; modo manual no duplica; `manifest_mismatch` bloquea.
  - Evidencia: pytest y conteo de eventos/componentes.

- [ ] T052 [P] [US2] Escribir `tests/unit/test_delivery_recovery.py`.
  - Depende de: T041.
  - Comprobación: timeout → `uncertain`; reinicio → `uncertain/interrupted`; parcial → solo documento se reintenta; resumen aceptado no se reenvía; importación intacta; **revocación de consentimiento entre resumen y PDF** conserva el resumen aceptado y deja el documento `skipped` con motivo.
  - Evidencia: pytest con reloj/estado simulado y salida de estados; cubre T041.

- [ ] T053 [P] [US2] Escribir `tests/unit/test_delivery_privacy.py` y `tests/contract/test_manual_delivery.py`; T053 es dueña de ambos y T038/T043/T045 no los crean.
  - Depende de: T038, T043, T045.
  - Comprobación: sin IP/nombres internos/Results/título sensible por defecto; alias; errores sin secretos; aislamiento entre casos; 409/422 correctos.
  - Evidencia: pytest y búsqueda de cadenas prohibidas.

- [ ] T054 [P] [US4] Escribir `tests/contract/test_notification_history.py`; T054 es dueña y T045 no lo crea.
  - Depende de: T045, T047.
  - Comprobación: historial muestra versión, modo, regla (nula en manual), destinatarios, contenido, estado por componente, fechas e id; distingue aceptado de entregado/leído.
  - Evidencia: pytest y captura de la vista.

- [ ] T055 [US2] Escribir `tests/acceptance/test_manual_notification_journey.py`.
  - Depende de: T049–T054.
  - Comprobación: recorrido contacto → código → verificación → consentimiento → vínculo → vista previa → confirmación → envío con doble → estados; sin red externa.
  - Evidencia: pytest y registro del transporte doble.

- [ ] T056 [US2] Documentar el Corte B en `docs/evidencia/006-corte-b/README.md` y actualizar `docs/planificacion/006-ultimo-resultado.md`.
  - Depende de: T055.
  - Comprobación: comandos, resultados, capturas, límites de verificación, manifiesto, idempotencia y pendientes.
  - Evidencia: documento revisado y enlaces.

**Checkpoint B**: contacto verificado y envío manual completo, con eventos y recuperación, sin depender de reglas.

---

## Phase 5: Corte C — Reglas automáticas y aceptación integrada (US3, P3; US4)

**Goal**: configurar reglas por caso, disparar solo tras una importación confirmada, conservar la
versión generada, revalidar antes de enviar y evitar duplicados entre modos.

**Independent Test**: activar una regla con destinatarios verificados, confirmar una importación que
coincide, comprobar el informe y los envíos automáticos; reiniciar y verificar que reutiliza la misma
versión y no duplica; con la regla desactivada, cero envíos.

### Migración y servicios de reglas

- [ ] T057 [US3] Crear la migración `alembic/versions/<rev>_add_notification_rules.py` y actualizar `src/secguard_advisor/db/models.py`.
  - Depende de: T035.
  - Comprobación: crea `notification_rules`, `notification_rule_contacts` y `notification_rule_evaluations`; `Unique(case_id, version)`, `Unique(rule_id, import_id)`, `status IN ('draft','active','disabled','superseded')`, `trigger_type='qualys_import_confirmed'`; `notification_rule_evaluations.generation_key` String(64) UNIQUE no nulo; `report_version_id` FK `report_versions.id`; no crea tablas de eventos (ya existen en B).
  - Evidencia: revisión Alembic, upgrade/downgrade; T057 implementa y crea `tests/unit/test_notification_rules_migration.py` con `generation_key`.

- [ ] T058 [P] [US3] Implementar reglas versionadas en `src/secguard_advisor/notifications/rules.py`.
  - Depende de: T057.
  - Comprobación: nueva regla `draft` desactivada; activar exige destinatarios verificados, consentidos y vinculados, autor y hash; cambiar destinatarios/condiciones/política crea versión nueva y exige reactivación; desactivar bloquea.
  - Evidencia: cubierto por T066 (`test_notification_rules.py`); T058 no crea el archivo.

- [ ] T059 [P] [US3] Implementar la evaluación durable en `src/secguard_advisor/notifications/evaluations.py`.
  - Depende de: T057.
  - Comprobación: `Unique(rule_id, import_id)`; estados `pending|claimed|done|skipped|failed`; `report_version_id` se fija al generar y no se sustituye; `reason_code`/`error_code` acotados.
  - Evidencia: cubierto por T067 (`test_rule_evaluation.py`); T059 no crea el archivo.

- [ ] T060 [US3] Conectar la confirmación de importación con el encolado en `src/secguard_advisor/vulnerabilities/service.py` y `src/secguard_advisor/notifications/evaluations.py`.
  - Depende de: T059.
  - Comprobación: la confirmación crea evaluaciones para reglas activas del caso en la misma transacción; staging/rechazo/cancelación/vista previa no encolan; una importación idéntica no duplica.
  - Evidencia: cubierto por T067 (`test_import_rule_enqueue.py`); T060 no crea el archivo.

- [ ] T061 [US3] Extender el ejecutor para reglas, `generation_key` y retención de versión en `src/secguard_advisor/notifications/executor.py`.
  - Depende de: T041, T058, T059.
  - Comprobación: usa `generation_key = auto:<evaluation.id>`; crea o recupera la versión con `INSERT ... ON CONFLICT(generation_key) DO NOTHING` y lectura posterior; si el proceso cae antes de guardar `report_version_id`, el reintento recupera la versión; si cae después, reutiliza versión y eventos; no crea otra versión para eludir idempotencia; llama a Telegram fuera de transacción.
  - Evidencia: cubierto por T068 (`test_rule_recovery.py`, `test_rule_executor.py`, `test_rule_generation_crash.py`).

- [ ] T062 [US3] Revalidar regla, consentimiento, destinatarios y manifiesto **antes de cada componente** en `src/secguard_advisor/notifications/delivery.py` y `src/secguard_advisor/notifications/rules.py`.
  - Depende de: T061.
  - Comprobación: antes del resumen y del PDF; regla activa y versión vigente; contactos verificados/consentidos/vinculados; manifiesto recalculado coincide; si algo cambió, conserva el componente aceptado y marca los restantes `skipped` con motivo y cero llamadas.
  - Evidencia: cubierto por T069 (`test_rule_revalidation.py`), que incluye revocación entre componentes.

- [ ] T063 [US3] Implementar recuperación y cruce de modos sin duplicados en `src/secguard_advisor/notifications/executor.py` y `src/secguard_advisor/notifications/delivery.py`.
  - Depende de: T061, T062.
  - Comprobación: reinicio reutiliza versión y eventos; timeout → `uncertain` sin reintento automático; manual/automático comparten `idempotency_key`; componente aceptado no se reenvía.
  - Evidencia: cubierto por T070 (`test_cross_mode_delivery.py`) y T068 (`test_rule_recovery.py`); T063 no crea los archivos.

### Rutas y UI

- [ ] T064 [US3] Crear rutas de reglas en `src/secguard_advisor/web/routes/notification_rules.py` e incluirlas en `src/secguard_advisor/web/app.py`.
  - Depende de: T058, T060.
  - Comprobación: listar/crear/activar/desactivar; crear no activa; activar valida; cambios exigen nueva versión; 422/409 claros; no envía en GET.
  - Evidencia: cubierto por T066 (`test_rule_routes.py`); T064 no crea el archivo.

- [ ] T065 [P] [US3] Crear plantillas de reglas en `src/secguard_advisor/web/templates/notifications/_rules.html` y `_rule_form.html`.
  - Depende de: T064.
  - Comprobación: caso, destinatarios, disparador, condiciones, contenido, detalle, `synthesis_policy`, autor, versión, estado y fechas; desactivada por defecto; advertencia de autorización previa; responsive.
  - Evidencia: cubierto por T066/T072 (captura y renderizado).

### Pruebas del Corte C

- [ ] T066 [P] [US3] Escribir `tests/unit/test_notification_rules.py` y `tests/contract/test_rule_routes.py`; T066 es dueña de ambos y T058/T064 no los crean.
  - Depende de: T058, T064.
  - Comprobación: draft por defecto; activación válida; cambio exige reactivación; desactivación; rutas y códigos.
  - Evidencia: pytest y captura de estados.

- [ ] T067 [P] [US3] Escribir `tests/unit/test_rule_evaluation.py` y `tests/integration/test_import_rule_enqueue.py`; T067 es dueña de ambos y T059/T060 no los crean.
  - Depende de: T059, T060.
  - Comprobación: solo importación confirmada y coincidente; staging/rechazo/cancelación/vista previa cero; duplicado no reevalúa; encolado en la misma transacción.
  - Evidencia: pytest y consulta a `notification_rule_evaluations`.

- [ ] T068 [P] [US3] Escribir `tests/unit/test_rule_recovery.py`, `tests/unit/test_rule_executor.py` y `tests/unit/test_rule_generation_crash.py`.
  - Depende de: T061.
  - Comprobación: reinicio reutiliza `generation_key` y `report_version_id`; interrupción **antes de guardar el vínculo** recupera la versión por la clave; interrupción **después del vínculo** reutiliza versión y eventos; no crea versión nueva; no reenvía aceptados; `uncertain` no se reintenta automáticamente.
  - Evidencia: pytest con dos arranques simulados, conteo de versiones/eventos y prueba de los dos puntos de interrupción; cubre T061.

- [ ] T069 [P] [US3] Escribir `tests/unit/test_rule_revalidation.py`.
  - Depende de: T062.
  - Comprobación: regla desactivada, contacto revocado, consentimiento retirado, vínculo eliminado o manifiesto alterado → cero llamadas y motivo registrado; revocación entre resumen y PDF conserva el resumen aceptado y bloquea el documento.
  - Evidencia: pytest y estados `partial`/`skipped`; cubre T062.

- [ ] T070 [P] [US3] Escribir `tests/unit/test_cross_mode_delivery.py`.
  - Depende de: T063.
  - Comprobación: manual y automático para misma versión/destinatario reutilizan evento; no duplican; el cruce queda en evidencia.
  - Evidencia: pytest y conteo de eventos/componentes.

- [ ] T071 [P] [US3] Ampliar `tests/unit/test_automatic_synthesis_policy.py` sobre `test_report_synthesis.py`.
  - Depende de: T021, T061, T062.
  - Comprobación: `factual_only` no llama a IA; `ai_if_budget` sin reserva no llama; con reserva registra `Run(kind='report')` y costo; no hay gasto recurrente; reutiliza las validaciones de `report-synthesis-v1` sin duplicarlas.
  - Evidencia: pytest con doble de proveedor y `ai_requests`; amplía T021.

- [ ] T072 [US3] Escribir `tests/acceptance/test_report_notifications_journey.py`.
  - Depende de: T055, T066–T071.
  - Comprobación: recorrido A → B → C con datos ficticios; regla activa, importación confirmada, informe, envío automático, historial y reinicio; sin red externa.
  - Evidencia: pytest y registro del transporte doble.

- [ ] T073 [US3] Escribir `tests/acceptance/test_006_regression.py` y ejecutar `make check`.
  - Depende de: T072.
  - Comprobación: 001–005 siguen pasando; navegación de escritorio/móvil; sin regresiones en chat, documentos, vulnerabilidades, IA y Qdrant; externas siguen omitidas sin autorización.
  - Evidencia: `make check`, integraciones afectadas y salida de pytest.

- [ ] T074 [US4] Escribir la matriz de aceptación SC-001–SC-012 en `docs/evidencia/006-corte-c/matriz-sc.md`.
  - Depende de: T072, T073.
  - Comprobación: cada SC tiene escenario, comando, resultado y evidencia; los no ejecutados se declaran pendientes (envío real, llamadas pagadas).
  - Evidencia: matriz revisada y enlaces.

- [ ] T075 [US3] Documentar el Corte C en `docs/evidencia/006-corte-c/README.md` y actualizar `docs/planificacion/006-ultimo-resultado.md`.
  - Depende de: T074.
  - Comprobación: incluye reglas, versión retenida, recuperación, cruce de modos, regresión y pendientes.
  - Evidencia: documento revisado.

**Checkpoint C**: regla automática completa, recuperable y sin duplicados; aceptación integrada.

---

## Phase 6: Polish y cierre documental

- [ ] T076 [P] Actualizar `docs/planificacion/handoff-006.md` con estado final de los tres cortes.
  - Depende de: T075.
  - Comprobación: rutas, decisiones, verificaciones, pendientes reales y comandos reproducibles.
  - Evidencia: handoff revisado.

- [ ] T077 Actualizar `README.md` y `AGENTS.md` con el estado real de 006.
  - Depende de: T076.
  - Comprobación: no se presenta Telegram, PDF ni reglas como implementados antes de su aceptación; se documentan Node/Playwright y límites.
  - Evidencia: diff revisado.

- [ ] T078 [P] Revisar seguridad y privacidad en `docs/evidencia/006-corte-c/seguridad.md`.
  - Depende de: T075.
  - Comprobación: token fuera de SQLite/UI/logs; chat no completo; sin IP/nombres internos/Results; LangSmith solo metadatos; errores sin secretos; aislamiento por caso.
  - Evidencia: checklist firmada por revisión local y pruebas citadas.

- [ ] T079 [P] Verificar que no se introdujo P1–P4, no se retomó 003 y que Fixed es antecedente histórico en `src/secguard_advisor/reports/` y `src/secguard_advisor/web/templates/`.
  - Depende de: T075.
  - Comprobación: búsqueda de `P1`–`P4` en código/UI de 006 sin resultados funcionales; `fixed` separado de pendientes; sin etiquetas de prioridad.
  - Evidencia: `rg` y revisión de plantillas.

- [ ] T080 Ejecutar la verificación final reproducible con `Makefile` y `alembic/versions/`.
  - Depende de: T076–T079.
  - Comprobación: `make check` verde; integraciones afectadas verdes; externas omitidas; `uv run alembic upgrade head` en base temporal; sin envíos reales ni llamadas pagadas.
  - Evidencia: salida completa y fecha.

- [ ] T081 Cerrar la documentación de pendientes reales en `docs/planificacion/006-ultimo-resultado.md`.
  - Depende de: T080.
  - Comprobación: se listan gate Playwright/Chrome, top 5 confirmado, título sensible, respaldo documental, envío real y presupuesto; nada se declara aceptado sin evidencia.
  - Evidencia: documento final revisado.

---

## Test Ownership

Cada archivo de prueba tiene **un único dueño**. Una tarea de implementación puede crear sus propias
pruebas; cuando no lo hace, remite al dueño y no las duplica. Las tareas posteriores solo amplían un
archivo existente cuando se indica expresamente.

| Archivo de prueba | Dueño | Alcance |
|---|---|---|
| `tests/unit/test_canonical_json.py` | T007 | JSON canónico y hash |
| `tests/unit/test_error_codes.py` | T010 | Códigos seguros |
| `tests/unit/test_reports_migration.py` | T012 | Migración A y `generation_key` |
| `tests/unit/test_report_aliasing.py` | T015 | Top 5 y alias |
| `tests/unit/test_report_charts.py` | T016 | Opciones y conclusiones |
| `tests/unit/test_report_artifacts.py` | T018 | Escritura atómica y hash |
| `tests/unit/test_report_synthesis.py` | T021 | `report-synthesis-v1`; T071 amplía el caso automático |
| `tests/contract/test_report_routes.py` | T023 | Rutas del informe |
| `tests/unit/test_report_metrics.py` | T027 | Métricas y denominadores |
| `tests/unit/test_report_dataset.py` | T028 | Dataset y snapshot |
| `tests/unit/test_report_service.py` | T028 | Versiones e inmutabilidad |
| `tests/contract/test_report_concordance.py` | T029 | Concordancia web/PDF |
| `tests/integration/test_report_pdf.py` | T030 | Comprobaciones automáticas con pypdf |
| `tests/acceptance/test_report_browser.py` | T031 | Navegador y revisión visual del PDF |
| `tests/unit/test_report_privacy.py` | T032 | Privacidad del contenido |
| `tests/contract/test_report_isolation.py` | T032 | Aislamiento entre casos |
| `tests/acceptance/test_report_journey.py` | T033 | Recorrido del Corte A |
| `tests/unit/test_notifications_manual_migration.py` | T035 | Migración B y desafío |
| `tests/unit/test_contacts.py` | T036 | Contactos y consentimiento |
| `tests/unit/test_contact_verification.py` | T049 | Desafío de verificación |
| `tests/unit/test_telegram_transport.py` | T038 | Transporte real/doble |
| `tests/unit/test_delivery_states.py` | T040 | Estados de eventos/componentes |
| `tests/unit/test_report_manifest.py` | T050 | Manifiesto |
| `tests/unit/test_confirmations.py` | T050 | Confirmación e invalidación |
| `tests/unit/test_delivery_idempotency.py` | T051 | Idempotencia y doble clic |
| `tests/unit/test_manual_send.py` | T051 | Envío manual |
| `tests/unit/test_delivery_recovery.py` | T052 | Reinicio, timeout y revocación entre componentes |
| `tests/contract/test_contact_verification_routes.py` | T049 | Rutas de verificación |
| `tests/contract/test_manual_delivery.py` | T053 | Contrato de envío manual |
| `tests/unit/test_delivery_privacy.py` | T053 | Privacidad de entrega |
| `tests/contract/test_notification_history.py` | T054 | Historial y auditoría |
| `tests/acceptance/test_manual_notification_journey.py` | T055 | Recorrido manual |
| `tests/unit/test_notification_rules_migration.py` | T057 | Migración C |
| `tests/unit/test_notification_rules.py` | T066 | Reglas versionadas |
| `tests/contract/test_rule_routes.py` | T066 | Rutas de reglas |
| `tests/unit/test_rule_evaluation.py` | T067 | Evaluación durable |
| `tests/integration/test_import_rule_enqueue.py` | T067 | Encolado tras importación |
| `tests/unit/test_rule_recovery.py` | T068 | Recuperación de reglas |
| `tests/unit/test_rule_executor.py` | T068 | Ejecutor automático |
| `tests/unit/test_rule_generation_crash.py` | T068 | Interrupción antes/después del vínculo |
| `tests/unit/test_rule_revalidation.py` | T069 | Revalidación por componente |
| `tests/unit/test_cross_mode_delivery.py` | T070 | Cruce manual/automático |
| `tests/unit/test_automatic_synthesis_policy.py` | T071 | Política automática; amplía T021 |
| `tests/acceptance/test_report_notifications_journey.py` | T072 | Recorrido integrado |
| `tests/acceptance/test_006_regression.py` | T073 | Regresión 001–005 |

**Tareas de implementación que crean sus pruebas**: T007, T010, T012, T015, T016, T018, T021, T023,
T035, T038, T040, T057. Las demás tareas de implementación no crean archivos de prueba; ejecutan la
prueba del dueño y reportan el resultado.

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (T001–T006)**: T001 primero; T002–T005 después de T001; T006 después de T002.
- **Foundational (T007–T011)**: depende de Setup; T007/T009/T010 después de T004; T008 después de
  T005; T011 después de T008.
- **Corte A (T012–T034)**: depende de Foundational; no depende de B/C.
- **Corte B (T035–T056)**: depende de Foundational y de la migración A (T012) por la FK a
  `report_versions`; no depende de C.
- **Corte C (T057–T075)**: depende de B completo (eventos/ejecutor) y de A (versiones); no crea tablas
  de eventos.
- **Polish (T076–T081)**: depende de los tres cortes.

### Critical Path

```text
A: T001 → T002 → T004 → T007 → T012 → T013 → T014 → T015 → T016 → T017/T019 → T020 → T022
   → T023 → T024/T026 → T029 → T030 → T031 → T033 → T034
B1: T012 → T035 → T036 → T037 → T044 → T049 → T055
B2: T035 → T038/T039 → T040 → T041 → T052 → T055
B3: T035 → T039/T040 → T041/T042 → T043 → T045 → T047 → T054 → T055
C1: T035 → T057 → T058/T059 → T060 → T061 → T062 → T063 → T064 → T072 → T073 → T080
C2: T055 + T066/T067/T068/T069/T070/T071 → T072 → T073 → T080
```

### Parallel Opportunities

- **Setup**: tras T001, T002/T003/T004/T005; T006 tras T002.
- **Foundational**: tras T004/T005, T007/T008/T009/T010; T011 tras T008.
- **Corte A**: tras T012, T013/T018/T021; después T014, T015, T016, T017/T019, T020; tras T023,
  T024/T025/T026; después T027–T030 y T032; T031 tras T030; T033 al final.
- **Corte B**: tras T035, T036/T038/T039; después T037, T040; T041/T042; T043; T044/T045; tras T044,
  T046/T048; tras T045, T047; T049–T054 según sus dependencias; T055 al final.
- **Corte C**: tras T057, T058/T059; después T060, T061; T062; T063/T064; T065/T066/T067/T068/T069/T070/T071 según dependencias; T072 al final.
- **No paralelas**: T014/T015/T016, T033 con T027–T032, T037 con T036, T041/T042 con T043,
  T031 con T030, T061/T062/T063 cuando comparten `executor.py`/`delivery.py`, T077 con T076.

### Story Dependencies

- **US1**: independiente tras Foundational.
- **US2**: depende de US1 solo por `report_versions`; no depende de C.
- **US3**: depende de US2 por eventos/ejecutor y de US1 por versiones.
- **US4**: auditoría en B (historial manual) y C (reglas/automático).

---

## Parallel Example: Corte A

```bash
# Tras T012 (no paralelizar T013 con T014/T015/T016):
Task: "T013 dataset canónico en reports/dataset.py"
Task: "T018 artefactos atómicos en reports/artifacts.py"
Task: "T021 síntesis en reports/synthesis.py"

# Después de T013:
Task: "T014 métricas"
# Después de T014:
Task: "T015 alias top 5"
# Después de T015:
Task: "T016 opciones ECharts"

# Tras T023:
Task: "T024 plantillas de informe"
Task: "T025 gráficas interactivas"
Task: "T026 navegación"
```

## Parallel Example: Corte B

```bash
# Tras T035:
Task: "T036 contactos y consentimiento"
Task: "T038 transporte Telegram"
Task: "T039 manifiesto canónico"

# Después de T036:
Task: "T037 desafíos de verificación"

# Después de T044 y T047:
Task: "T049 pruebas de verificación"
Task: "T050 pruebas de manifiesto/confirmación"
Task: "T051 pruebas de idempotencia"
Task: "T052 pruebas de recuperación"
Task: "T053 pruebas de privacidad/contrato"
Task: "T054 pruebas de historial"
```

## Parallel Example: Corte C

```bash
# Tras T057:
Task: "T058 reglas versionadas"
Task: "T059 evaluación durable"

# Con T061/T062/T063/T064 satisfechas según corresponda:
Task: "T066 pruebas de reglas/rutas"
Task: "T067 pruebas de encolado"
Task: "T068 pruebas de recuperación"
Task: "T069 pruebas de revalidación"
Task: "T070 pruebas de cruce de modos"
Task: "T071 pruebas de política de síntesis"
```

---

## Implementation Strategy

### MVP primero

1. Setup + Foundational.
2. Corte A completo.
3. Validar A de forma independiente: informe web/PDF, concordancia, privacidad y PDF.
4. Demo local con datos ficticios; sin envíos.

### Entrega incremental

1. A → informe verificable.
2. B → verificación, consentimiento y envío manual con dobles.
3. C → regla automática, recuperación y aceptación integrada.
4. Regresión 001–005 antes de cerrar.

### Reglas de ejecución

- Cada corte tiene su propia migración aditiva y su checkpoint.
- No se implementa C antes de que B tenga eventos, componentes, intentos y ejecutor.
- La generación automática usa `generation_key`; la recuperación no crea otra versión.
- Antes de cada componente se revalidan destinatario, consentimiento, vínculo, manifiesto y regla.
- Un componente aceptado no se reenvía; uno incierto no se reintenta automáticamente.
- pypdf solo cubre páginas/texto/objetos; la inspección visual del PDF es T031.
- Top 5 y título sensible son valores predeterminados, no decisiones pendientes.
- Todo envío de prueba usa `stub`; el envío real y las llamadas pagadas quedan para autorización
  posterior con destino, contenido y presupuesto concretos.
- No se introducen P1–P4 ni se retoma 003.

---

## Format Validation

- Todas las tareas usan `- [ ] TNNN` con ID único.
- Las tareas de historia llevan `[US1]`, `[US2]`, `[US3]` o `[US4]`.
- Las tareas paralelas llevan `[P]` solo cuando no comparten archivo ni dependencia incompleta.
- Cada tarea declara archivo(s), dependencia, comprobación observable y evidencia.
- Total: **81 tareas** (T001–T081).
