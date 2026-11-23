# Implementation Plan: Informe ejecutivo visual y notificaciones mediante Telegram

**Branch**: `006-informe-ejecutivo-telegram` (no creada) | **Date**: 2026-11-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/006-informe-ejecutivo-telegram/spec.md`, corregida con
FR-023 e idempotencia entre modos, y constitución 1.4.0.

## Summary

006 convierte una instantánea Qualys confirmada en un informe ejecutivo verificable, con una sola
fuente de datos persistida por versión, vista web interactiva, PDF con composición propia para
impresión y notificación por Telegram. La entrega se divide en tres cortes funcionales:

- **A. Informe ejecutivo web y PDF visual**: métricas deterministas en SQLite, dataset canónico,
  gráficas ECharts compartidas, PDF local e historial inmutable.
- **B. Contactos verificados y envío manual**: contactos/canales, verificación real del destino,
  consentimiento, vinculación por caso, confirmación individual y evento por destinatario.
- **C. Regla automática, recuperación y aceptación integrada**: regla versionada y desactivada por
  defecto, autorización previa, ejecutor recuperable tras reinicio, resultados parciales e inciertos.

La IA es opcional y acotada: por defecto el informe es factual; la síntesis usa el proveedor
configurado, presupuesto, redacción y telemetría existentes, y nunca calcula cifras. El envío
automático no concede gasto recurrente: sin reserva de presupuesto previa, el informe se genera sin
IA.

## Technical Context

**Language/Version**: Python 3.14.6; Node.js ≥26.11.1 <27 para assets y renderizado ECharts SSR.

**Primary Dependencies**: FastAPI, Jinja2, HTMX, Tailwind CSS 3.4.17, Flowbite 2.5.2, Apache ECharts
5.6.0, SQLAlchemy 2.1, Alembic, pypdf. Se añadirá `playwright` (Python) para PDF con Chrome local o
Chromium; no se instala en este paso.

**Storage**: SQLite como fuente de verdad (`storage/secguard.sqlite3`); artefactos inmutables en
`storage/reports/<case_id>/<report_id>/<version>/` (PDF y SVG de gráficas); token de Telegram solo en
`.env` como secreto.

**Testing**: pytest con unit, contract, integration y acceptance; Playwright para verificación visual
del HTML de impresión; pypdf para páginas, texto y objetos embebidos; transporte Telegram sustituible
por dobles.

**Target Platform**: aplicación local macOS/Linux, un proceso y un worker; navegador de escritorio y
móvil para la web; Telegram Bot API como único canal externo.

**Project Type**: aplicación web monolítica con renderizado en servidor y un ejecutor de
notificaciones en el mismo proceso.

**Performance Goals (objetivos por medir, no resultados obtenidos)**: informe factual sin IA ≤ 10 s;
PDF ≤ 15 s; vista web ≤ 2 s con datos ya persistidos; evaluación de regla y encolado ≤ 1 s tras
confirmar la importación; ninguna llamada externa dentro de una transacción SQLite.

**Constraints**: sin CDN, sin servicios externos de imágenes, sin OCR, sin envío real en pruebas, sin
transacción abierta durante HTTP, sin reintento ciego de timeout incierto, sin gasto recurrente
ilimitado y sin exponer token, chat_id completo, IP, nombres internos ni Results.

**Scale/Scope**: un caso por informe; 2–3 páginas de PDF; top 5 de activos por defecto; una versión
inmutable por regeneración; múltiples reglas activas posibles por caso, deduplicadas por
informe/versión + destinatario.

## Constitution Check

*GATE: aplicado antes del diseño y revalidado después.*

| Principio / regla | Verificación | Estado |
|---|---|---|
| I. Propósito y alcance | Acción operativa controlada, no remediación ni certificación | PASS |
| II. Construcción reproducible | uv, `uv.lock`, Alembic, assets locales, conventional commits | PASS |
| III. Arquitectura modular | Módulos `reports` y `notifications`; rutas y servicios separados | PASS |
| IV. Persistencia local e inferencia autorizada | SQLite fuente de verdad; IA opcional con presupuesto | PASS |
| V. Recuperación verificable | Cifras deterministas; citas no se mezclan con hechos CSV | PASS |
| VI. Separación de datos | Dataset por caso y snapshot; sin mezcla entre casos | PASS |
| VII. Seguridad | Alcance en código, token fuera de SQLite, redacción | PASS |
| VIII. Evidencia e incertidumbre | Estados, límites y resultados inciertos explícitos | PASS |
| IX. Revisión humana | Confirmación manual y autorización previa diferenciadas | PASS |
| X. Evaluación independiente | Pruebas con dobles; envío real posterior y autorizado | PASS |
| XI. Observabilidad y costos | Telemetría existente; LangSmith solo metadatos | PASS |
| XII. Desarrollo incremental | Cortes A, B y C verificables por separado | PASS |
| XIII. Frontera de datos y proveedores | Contenido permitido y autorización por caso | PASS |
| XIV. Acciones operativas controladas | Preparar → previsualizar → confirmar/regla → ejecutar → evidenciar | PASS (1.4.0) |
| Prohibición: sin CDN | ECharts y recursos locales; SVG generado localmente | PASS |
| Prohibición: sin segunda observabilidad | Se reutiliza `ai_requests`/LangSmith existentes | PASS |
| Prohibición: sin acciones sin control | Manual con confirmación; automático con regla activa | PASS (1.4.0) |

**Post-diseño**: PASS. No se requiere complejidad adicional ni excepción constitucional.

## Project Structure

### Documentation (this feature)

```text
specs/006-informe-ejecutivo-telegram/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── report-metrics.md
│   ├── report-synthesis.md
│   ├── web-routes.md
│   └── telegram-delivery.md
├── checklists/requirements.md
└── spec.md
```

### Source Code (repository root)

```text
src/secguard_advisor/
├── reports/
│   ├── __init__.py
│   ├── canonical.py        # JSON canónico y SHA-256 compartido
│   ├── dataset.py          # esquema canónico, hash y validación
│   ├── metrics.py          # cálculos deterministas en SQLite
│   ├── aliasing.py         # alias de activos y recorte declarado
│   ├── charts.py           # opciones ECharts compartidas web/PDF
│   ├── privacy.py          # política de contenido y alias
│   ├── errors.py           # códigos seguros de informe
│   ├── synthesis.py        # síntesis IA opcional y fallback factual
│   ├── artifacts.py        # escritura atómica, SHA-256 y rutas
│   ├── render.py           # HTML de impresión → PDF con Playwright
│   └── service.py          # ciclo de vida de informe y versiones
├── notifications/
│   ├── __init__.py
│   ├── errors.py           # códigos seguros de entrega
│   ├── contacts.py         # contactos, consentimiento y vínculos
│   ├── verification.py     # desafíos de código de verificación
│   ├── manifest.py         # report-manifest-v1
│   ├── confirmations.py    # confirmación manual y manifiesto
│   ├── delivery.py         # eventos, componentes, intentos e idempotencia
│   ├── executor.py         # outbox, trabajador y recuperación (B y C)
│   ├── manual.py           # orquestación del envío manual
│   ├── rules.py            # reglas versionadas y activación (C)
│   ├── evaluations.py      # evaluación durable de reglas (C)
│   └── channels/
│       ├── base.py         # interfaz TelegramTransport
│       └── telegram.py     # cliente HTTP, errores y redacción
├── web/routes/
│   ├── reports.py
│   ├── contacts.py
│   ├── notifications.py
│   └── notification_rules.py
└── web/templates/
    ├── reports/{view,print,_cards,_charts,_history,_notifications}.html
    ├── contacts/{index,_form,_verification}.html
    └── notifications/{_panel,_preview,_history,_rules,_rule_form}.html

scripts/render_report_charts.mjs        # ECharts SSR → SVG
alembic/versions/<rev>_add_reports_notifications.py
tests/{unit,contract,integration,acceptance}/...
```

## Delivery Cuts

### Corte A — Informe ejecutivo web y PDF

1. Migración aditiva para `reports`, `report_versions` (con `generation_key` único nullable),
   `report_artifacts` y extensión compatible de `runs` (`kind='report'`, `conversation_id` nullable,
   outcomes de informe). El Corte A no referencia tablas de C.
2. Gate temprano de Playwright + Chrome/Chromium. Si no se puede generar PDF, el corte se detiene y se
   reevalúa el motor; no se implementa un PDF degradado.
3. `metrics.py`: dataset determinista desde `qualys_imports` y `qualys_vulnerabilities` del snapshot;
   top 5 de activos por defecto y recorte declarado.
4. `charts.py` + `render_report_charts.mjs`: opciones ECharts y SVG estáticos. **Node participa** en
   el renderizado local de gráficas para PDF; se documenta como prerrequisito.
5. `render.py`: plantilla de impresión, CSS `@page`, PDF con Playwright.
6. Rutas `/cases/{case_id}/reports*`, navegación «Informe ejecutivo», tarjetas, gráficas, tablas y PDF.
7. Síntesis IA opcional con proveedor/presupuesto/telemetría existentes y fallback factual. Se separan
   hechos calculados, `agent_proposal` y respaldo documental.
8. Pruebas de concordancia SQLite → dataset → tarjetas → gráficas → PDF, privacidad e inmutabilidad.

**Salida verificable**: un informe generado desde una instantánea ficticia confirmada se ve igual en
web y PDF, con cifras concordantes y sin llamadas externas.

### Corte B — Contactos verificados y envío manual

1. Migración para `contact_channels`, `contact_case_links`, `contact_verification_challenges`,
   `report_confirmations`, `notification_events`, `notification_components` y
   `notification_attempts`. **No depende de tablas de reglas.**
2. Administración → «Contactos y canales»: alta, verificación y consentimiento. El envío del código
   de verificación se solicita desde la interfaz y es independiente del bloqueo de informes.
3. Desafío persistido: hash, expiración, intentos, consumo, contacto y bot; límites de solicitud y
   reintento; nunca código en claro ni token.
4. Vínculos autorizados por caso.
5. Manifiesto canónico de contenido aprobado (versión, texto saliente, hash del PDF, política y
   destinatarios) compartido por confirmación y ejecución.
6. Servicio de entrega y ejecutor del envío manual: eventos, componentes resumen/PDF, intentos,
   idempotencia, estados, errores y recuperación de resultados inciertos. Antes de cada componente se
   revalidan destinatario, consentimiento, vínculo y manifiesto; si se revoca, se conserva el
   componente aceptado y se bloquean los restantes.
7. Vista previa, confirmación, envío e historial en el caso.
8. Pruebas de verificación sin informe, destinatario no verificado, aislamiento, confirmación
   invalidada, doble clic, parcial, timeout y reinicio.

**Salida verificable**: con doble de Telegram, el código de verificación se envía a un contacto no
verificado aunque el informe esté bloqueado; un informe confirmado se envía solo si manifiesto y
destinatario coinciden; cada destinatario queda con estado por componente.

### Corte C — Regla automática, recuperación y aceptación integrada

1. Migración para `notification_rules`, `notification_rule_contacts` y
   `notification_rule_evaluations` (con `report_version_id`). Reutiliza la infraestructura de entrega
   del Corte B.
2. Regla versionada por caso, desactivada por defecto, con hash de condiciones y reactivación.
3. Encolado en la misma transacción de confirmación de importación; evaluación con
   `generation_key = auto:<evaluation.id>` que conserva la versión generada.
4. Recuperación tras reinicio: reutiliza `generation_key`, versión y eventos existentes; si el
   proceso cae antes de guardar el vínculo, recupera la versión por la clave; solicitudes sin
   resultado → `uncertain`; sin reintento ciego ni versión nueva para eludir idempotencia.
5. Revalidación de regla, consentimiento y destinatarios antes de enviar.
6. Resultado parcial resumen/PDF; reintento solo de componentes no aceptados; cruce manual/automático
   sin duplicados.
7. Aceptación integrada con dobles, navegación móvil/escritorio, regresión de 001–005 y evidencia.

**Salida verificable**: regla activa → importación confirmada → informe y envío automático
registrados sobre una versión estable; regla desactivada o importación no confirmada → cero envíos;
reinicio y timeout incierto no duplican, no reenvían componentes aceptados y no prometen entrega.

## Key Technical Decisions

1. **Una sola fuente por versión**: `report_versions.dataset_json` y `chart_specs_json` son la única
   entrada de tarjetas, gráficas, web y PDF. La vista y el PDF no recalculan ni consultan Qualys.
2. **PDF local con navegador real**: plantilla Jinja de impresión + Tailwind print + Playwright con
   Chrome del sistema (o Chromium) y `page.pdf()`. Se elige por fidelidad a Tailwind y verificación
   visual con captura; se descartan WeasyPrint (dependencias de sistema y soporte CSS parcial) y
   ReportLab (duplicaría la composición).
3. **Gráficas desde las mismas opciones**: web con `echarts.init` y PDF con ECharts SSR a SVG mediante
   `scripts/render_report_charts.mjs`; SVG embebido como data URI. Sin CDN ni rasterización externa.
4. **Cifras deterministas**: `metrics.py` calcula todo con SQL agregado sobre el snapshot; el modelo
   nunca produce números ni recibe filas crudas.
5. **Idempotencia por informe/versión + destinatario**: clave única SHA-256; el modo es metadato.
   Resumen y PDF son componentes independientes; un componente aceptado no se reenvía.
6. **Outbox en SQLite**: la confirmación de importación encola la evaluación de reglas en su misma
   transacción; el ejecutor reclama en transacción corta y llama a Telegram fuera de ella.
7. **Verificación de destino real**: chat_id no basta; `getChat` + código de un solo uso enviado al
   chat y confirmado en la aplicación, con evidencia y consentimiento separados.
8. **Privacidad por política de contenido**: alias de activos, sin IP, sin nombres internos, sin
   Results, sin filas crudas; vista previa de lo que saldrá.
9. **IA opcional y acotada**: por defecto factual; si se habilita, reutiliza proveedor, autorización
   por caso, presupuesto, redacción y telemetría (`Run` con `kind='report'`, sin conversación) para
   no duplicar observabilidad; sin reserva no hay llamada. Sin gasto recurrente.
10. **Artefactos inmutables**: PDF y SVG se escriben una vez con nombre determinista, SHA-256 en
    SQLite; regenerar crea otra versión. No se promete reproducibilidad byte a byte del navegador.
11. **Cortes independientes**: B incluye eventos, componentes, intentos y ejecutor manual; C añade
    reglas y evaluación reutilizando esa infraestructura. Ningún corte depende de tablas futuras.
12. **Manifiesto aprobado**: confirmación y ejecución comparten un manifiesto canónico; la ejecución
    verifica versión, texto, hash del PDF, política y destinatarios antes de llamar a Telegram.
13. **Generación recuperable**: `report_versions.generation_key` único nullable; automático usa
    `auto:<evaluation_id>` y recupera la versión por la misma clave antes o después del vínculo.
14. **Revalidación por componente**: el ejecutor compartido revalida destinatario, consentimiento,
    vínculo, manifiesto y regla antes del resumen y del PDF, en manual y automático.
15. **Síntesis canónica**: `report-synthesis-v1` usa `claim_refs` estructurados y citas verificadas;
    la validación literal no garantiza respaldo semántico. Resumen y focos son plantillas
    deterministas; el modelo solo propone recomendaciones.
16. **Controles 005**: autorización por alcance, procedencia `synthetic_public`, presupuesto,
    reserva/liquidación, contexto y concurrencia. Qualys privado nunca sale a un proveedor externo.
17. **Generación recuperable**: `report_versions.status` (`generating`/`ready`/`failed`), artefactos
    temporales, publicación atómica lógica y limpieza acotada; sin transacción durante modelo o PDF.
18. **Validación estricta**: todos los textos se validan; contradicciones de ausencia, cifras libres,
    IP/nombres internos y citas inexistentes producen fallback factual.

## Non-Functional Targets

- Accesibilidad: contraste, texto alternativo, tablas equivalentes, foco visible, navegación por
  teclado y etiquetas `aria` en gráficas.
- Responsive: tarjetas y gráficas apiladas en móvil; acciones principales visibles sin menús ocultos.
- Rendimiento: render de vista con dataset persistido; PDF en proceso separado del request cuando sea
  posible, con estado `generating` y reintento manual.
- Seguridad: token `SecretStr`; logs con redacción; sin `chat_id` completo en logs; errores con
  códigos estables.
- Observabilidad: eventos y componentes persistidos; telemetría de IA en `ai_requests`; LangSmith solo
  metadatos acotados.

## Risks and Mitigations

| Riesgo | Mitigación |
|---|---|
| Playwright/Chrome no disponible en el entorno | Gate de entorno antes de implementar; si falla, reevaluar WeasyPrint explícitamente, sin fallback silencioso |
| PDF con páginas vacías o gráficas cortadas | `break-inside: avoid`, alturas fijas, aserción de 2–3 páginas, texto por página y revisión visual |
| Cifras divergentes entre web/PDF | Un dataset y un hash; prueba de concordancia y snapshot de opciones |
| Duplicado manual/automático | Clave única por versión+destinatario y prueba de cruce de modos |
| Timeout incierto con reintento ciego | Estado `uncertain` persistido; reintento solo manual y de componentes no aceptados |
| Gasto recurrente al activar regla | Síntesis automática `factual_only` por defecto; reserva previa y tope por ejecución |
| Fuga de datos a Telegram/LangSmith | Política de contenido, alias, redacción y pruebas de privacidad |
| Migración sobre datos existentes | Migración aditiva, sin tocar tablas de 002–005; `alembic upgrade head` verificado |

## Complexity Tracking

No hay violaciones constitucionales ni complejidad que justificar. La única dependencia nueva
(`playwright`) reemplaza a un motor PDF inexistente y se evalúa con un gate de entorno.

## Defaults confirmados y pendientes reales

**Defaults confirmados**: top 5 de activos como valor predeterminado y título del caso excluido del
contenido saliente (`include_case_title=false`). No son decisiones bloqueantes.

**Pendientes reales**:

- Confirmar en implementación si se usa Chrome del sistema o Chromium empaquetado.
- Decidir si se habilita respaldo documental con recuperación en la síntesis o queda como propuesta
  sin cita en el primer corte.
- Autorización posterior para envío real de prueba con destino y contenido concretos.
- Autorización y presupuesto para llamadas pagadas.
