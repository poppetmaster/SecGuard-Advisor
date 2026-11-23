# Research — 006 Informe ejecutivo y notificaciones Telegram

**Fecha**: 2026-11-23
**Insumos**: `spec.md`, constitución 1.4.0, código vigente de FastAPI/Jinja/HTMX/ECharts/SQLite,
módulos `vulnerabilities`, `ai_config`, `ai_usage`, `evidence` y `web`.

## R1. Renderizado de PDF

**Decisión**: plantilla Jinja de impresión + CSS `@page` de Tailwind + Playwright (Python) con Chrome
del sistema (`channel="chrome"`) o Chromium, `page.pdf()` en A4.

**Razón**: el producto ya usa Tailwind/Flowbite de forma intensiva. Un navegador real interpreta el
mismo CSS, evita duplicar la composición y permite verificación visual con captura. El PDF no es una
captura de pantalla: es un documento de impresión con saltos, márgenes y tipografía propios.

**Alternativas**:

- *WeasyPrint*: HTML→PDF en Python, pero requiere Pango/HarfBuzz/Cairo del sistema y su soporte de
  flex/grid y utilidades Tailwind es parcial; riesgo alto de PDF distinto a la web.
- *ReportLab*: control preciso y sin binarios, pero obliga a reconstruir toda la composición y a
  convertir SVG; duplica mantenimiento y no reutiliza la plantilla.
- *Captura larga*: prohibida por la especificación y deficiente para impresión.

**Gate**: antes de implementar se verifica que Playwright pueda lanzar Chrome o Chromium en el
entorno objetivo. Si no, se reevalúa WeasyPrint con decisión explícita; no hay fallback silencioso.

## R2. Gráficas estáticas para el PDF

**Decisión**: `scripts/render_report_charts.mjs` usa el paquete `echarts` 5.6.0 ya fijado en
`package.json` y renderiza cada opción con `renderer: "svg", ssr: true`. El SVG se guarda como
artefacto y se embebe en el HTML de impresión como data URI.

**Razón**: una sola definición de opciones alimenta la web interactiva y el PDF; no hay CDN, servicio
de imágenes ni rasterización. El SVG es nítido y verificable.

**Alternativas**: captura PNG desde el navegador (menos nítida y dependiente de viewport), servicio
externo (prohibido), reconstruir gráficas en Python (duplicaría opciones).

**Nota**: el renderizado de gráficas es un paso de generación; si Node falla, el informe queda en
estado `failed` y no se publica un PDF sin gráficas.

## R3. Fuente única de datos por versión

**Decisión**: persistir `dataset_json` y `chart_specs_json` canónicos en `report_versions`; la vista
web, el HTML de impresión y el PDF leen exclusivamente esa fila. El hash canónico
(`sort_keys`, separadores compactos, UTF-8) se guarda en `dataset_sha256`.

**Razón**: elimina divergencias por recálculo o por cambios posteriores en Qualys; permite probar
concordancia y auditar qué se envió.

**Alternativas**: recalcular en cada vista (rompe inmutabilidad), guardar solo HTML (dificulta
pruebas y reutilización), guardar PDF como única fuente (no alimenta la web).

## R4. Motor de métricas

**Decisión**: `metrics.py` calcula todo con SQL agregado sobre `qualys_vulnerabilities` filtrado por
`case_id` + `import_id` del snapshot confirmado. Cada tarjeta y gráfica declara su universo y
denominador. Los conteos usan `COUNT(*)` sobre filas de vulnerabilidad, nunca `COUNT(DISTINCT cve)`
ni `JOIN` a CVEs en agregados.

**Razón**: evita multiplicación por CVE y hace explícitos los denominadores. `manual_review` se
calcula una vez como unión (estado desconocido o indicador indeterminado), coherente con
`manual_review_rows` de 002.

**Alternativas**: reutilizar los JSON de resumen del import (insuficiente para activos y gráficas),
delegar al modelo (prohibido).

## R5. Identificación y alias de activos

**Decisión**: el identificador es `asset_label` (FQDN > DNS > NetBIOS > IP; `Sin activo` cuando no
hay ninguno). Para contenido saliente se usa un alias determinista `Activo 01..N` ordenado por
críticos, altos, total pendiente y etiqueta ascendente. El dataset conserva la etiqueta interna para
la vista local; el PDF y el mensaje usan solo alias y declaran el recorte y los registros sin activo.

**Razón**: cumple privacidad sin perder trazabilidad numérica y evita que un nombre interno salga del
equipo.

**Alternativas**: hash del nombre (ilegible), ocultar activos (pierde foco), mostrar nombres internos
por defecto (viola privacidad).

## R6. Síntesis con IA

**Decisión**: esquema `report-synthesis-v1` documentado en `contracts/report-synthesis.md` con
`summary`, `focus[]`, `recommendations[]` y `limitations[]`. Cada recomendación declara `basis`
(`csv_fact`, `documentary`, `agent_proposal`), `claim_refs[]` y `evidence_refs[]`.

- Las cifras y afirmaciones cuantitativas se construyen desde campos estructurados del dataset con
  valor, unidad y denominador; la plantilla renderiza el número. No se prohíben todos los dígitos:
  se permiten identificadores válidos (informe, versión, QID, CVE, fechas) y se rechazan números
  libres que no correspondan a un `claim_ref`.
- Que un número exista en el dataset no valida la afirmación: el `claim_ref` debe identificar la
  métrica, el tipo de afirmación (conteo, proporción o comparación) y el denominador.
- `documentary` exige `evidence_refs` que resuelven a una cita existente y aceptada por el validador.
  La validación literal comprueba existencia e identidad, **no respaldo semántico**. Sin respaldo
  semántico comprobado, la recomendación se muestra como propuesta.
- Si falla el esquema, no hay respuesta, no cabe en presupuesto o el proveedor no está autorizado, se
  persiste un informe factual con `synthesis_status != completed` y la etiqueta «Sin síntesis de IA».

**Razón**: el modelo redacta, no calcula. Se reutilizan `ai_config`, autorización por caso,
presupuesto y `ai_requests`. El envío automático usa `factual_only` por defecto; con `ai_if_budget`
se reserva antes de llamar y el tope es por ejecución, no recurrente.

**Telemetría sin duplicar**: la síntesis crea un `Run` con `kind='report'`, `conversation_id` nulo y
`prompt_version='report-synthesis-v1'`. Así `ai_requests`, `provider_usage` y
`provider_budget_ledger` registran uso y costo sin una segunda plataforma. Las filas de chat no
cambian; las vistas de chat y ejecución filtran `kind='chat'`.

**Alternativas**: permitir números generados (riesgo de contradicción), generar siempre (gasto),
citas inventadas (prohibido).

**Pendiente real**: el respaldo documental con recuperación y citas verificadas se representa en el
esquema; en el primer corte las recomendaciones sin fuente se rotulan `agent_proposal` y «sin
respaldo documental». Se decide si se integra recuperación documental en un corte posterior.

## R7. Verificación del destino Telegram

**Decisión**: se separan dos envíos técnicos distintos:

- **Código de verificación**: solicitado explícitamente desde la interfaz. No exige que el contacto
  esté verificado, ni consentimiento, ni vínculo al caso; de lo contrario sería imposible verificar
  un contacto nuevo. Solo exige token configurado, contacto existente y límites de solicitud.
- **Informe**: exige contacto `verified`, consentimiento `granted`, vínculo `authorized` y regla/
  confirmación vigentes. El bloqueo de informes no bloquea el código.

Procedimiento del código:

1. La persona registra alias y chat_id; la aplicación valida formato y consulta `getChat` (y
   `getChatMember` para grupos) con el token de `.env`.
2. La aplicación crea `contact_verification_challenges` con `code_sha256`, `bot_fingerprint`,
   `expires_at` (10 min), `attempts`, `max_attempts=3`, `request_count` y `window_started_at`.
3. `sendMessage` envía el código de 6 dígitos. El código en claro no se persiste ni se registra.
4. Quien controla el destino introduce el código en la interfaz. Solo un desafío `pending`, no
   expirado y con intentos disponibles puede consumirse; al acertar pasa a `consumed`.
5. Se registran `verified_by`, `verified_at`, método, evidencia acotada y `chat_fingerprint`.
6. El consentimiento se registra aparte y la vinculación al caso se autoriza por separado.

Límites: máximo 3 solicitudes por ventana y 3 intentos por desafío; un nuevo envío invalida el
desafío anterior. El token permanece en `.env` y nunca se persiste.

**Razón**: evita el error de considerar suficiente un chat_id copiado y evita bloquear la verificación
por requisitos que solo aplican al informe.

**Alternativas**: `getChat` solo (insuficiente), webhook (infraestructura adicional), reutilizar el
envío de informes para el código (bloqueo circular).

## R8. Contenido aprobado, idempotencia y cruce de modos

**Decisión**:

- `report-manifest-v1` es el contrato único de contenido aprobado: caso, informe, versión,
  `dataset_sha256`, `outbound_text` y su hash, `pdf_sha256`, política de contenido, destinatarios y
  hash de destinatarios.
- La confirmación manual guarda `manifest_json` + `manifest_sha256`; la regla automática construye el
  mismo manifiesto al generar el informe.
- Antes de enviar, el ejecutor recalcula el manifiesto y compara `manifest_sha256`; si no coincide,
  no llama a Telegram.
- `idempotency_key = SHA-256(case_id | report_version_id | contact_id)` con índice único en
  `notification_events`. El modo no forma parte de la clave.
- Componentes `summary` y `document` con estado propio y restricción única por evento+tipo.

**Razón**: una sola definición de «aprobado» evita que la UI confirme algo distinto de lo que se
envía. El cruce manual/automático reutiliza el evento y no reenvía lo aceptado. La síntesis no se
presenta como hecho: resumen y focos son deterministas y la prosa libre es propuesta.

**Alternativas**: confirmar solo el texto (no cubre PDF ni destinatarios), hash por modo (permite
duplicar), comparar contenido en memoria (se pierde al reiniciar).

## R9. Cortes independientes, outbox y ejecutor recuperable

**Decisión**:

- **Corte B** incluye `notification_events`, `notification_components`, `notification_attempts` y el
  ejecutor del envío manual. No depende de `notification_rules`.
- **Corte C** añade reglas y `notification_rule_evaluations`; reutiliza el ejecutor y los eventos de
  B.
- La confirmación de importación encola evaluaciones en la misma transacción. El ejecutor:
  1. reclama un trabajo en transacción corta (`BEGIN IMMEDIATE`) con `claimed_at`;
  2. confirma la transacción;
  3. evalúa regla, consentimiento, destino, manifiesto y presupuesto;
  4. crea o reutiliza la versión y los eventos;
  5. llama a Telegram fuera de toda transacción;
  6. persiste el resultado en otra transacción corta.
- `notification_rule_evaluations.generation_key = "auto:" + evaluation.id` es único y estable. La
  creación o recuperación de `report_versions` usa `generation_key` con `INSERT ... ON CONFLICT DO
  NOTHING` y lectura posterior. Si el proceso cae antes de guardar `report_version_id`, el reintento
  recupera la versión por la misma clave; si cae después, reutiliza versión y eventos. Nunca se crea
  una versión nueva para eludir la idempotencia. El Corte A no referencia tablas de C.
- Antes de cada componente (resumen y PDF), el ejecutor compartido revalida destinatario,
  consentimiento, vínculo, manifiesto y regla si aplica. Si se revoca entre componentes, conserva el
  aceptado y marca los restantes `skipped`.
- Al arrancar, todo componente `requested` sin resultado pasa a `uncertain`; no se reintenta solo.

**Razón**: cada corte se verifica sin tablas futuras y la recuperación no crea versiones nuevas para
eludir la idempotencia.

**Alternativas**: todo el esquema en B (acopla cortes), versión nueva por reintento (duplica envíos),
cola externa (fuera de alcance), transacción larga (bloqueo).

## R10. Estados de entrega

**Decisión**:

- Desafío: `pending`, `consumed`, `expired`, `locked`.
- Evento: `prepared`, `queued`, `sending`, `accepted`, `partial`, `failed`, `uncertain`, `skipped`.
- Componente: `prepared`, `requested`, `accepted`, `failed`, `uncertain`, `skipped` (incluido el
  bloqueo por revalidación antes de un componente posterior).
- Intento: `requested`, `accepted`, `failed`, `uncertain`.

`accepted` significa que Telegram aceptó la solicitud; nunca «entregado» ni «leído». Si el resumen se
acepta y el PDF falla, el evento es `partial` y solo se reintenta el documento. Un timeout produce
`uncertain` y exige decisión humana; no se reintenta automáticamente.

**Alternativas**: un solo estado por envío (no distingue parcial), «delivered» (no verificable).

## R11. Privacidad y frontera de datos

**Decisión**: política de contenido versionada, incluida en el manifiesto. Por defecto: alias de
activos, sin IP/DNS/NetBIOS/FQDN, sin nombres internos, sin Results, sin filas crudas, sin CVEs
detallados, sin token y **sin título del caso** cuando se marca como sensible (`include_case_title`
`false` por defecto). La vista previa muestra el texto y el PDF exactos antes de confirmar. LangSmith
recibe solo metadatos (ids, proveedor, modelo, tokens, costo, estado), nunca texto, dataset, chat ni
token.

**Alternativas**: permitir todo con advertencia (no cumple), ocultar el contenido (impide
confirmación informada).

## R12. Migración y almacenamiento de artefactos

**Decisión**: una migración aditiva de Alembic crea las tablas nuevas; no se alteran tablas de
002–005. Los artefactos van a `storage/reports/<case_id>/<report_id>/<version>/` con escritura
temporal + `os.replace` y SHA-256 en SQLite. Nunca se sobrescribe un artefacto de una versión
publicada.

**Razón**: cumple inmutabilidad y permite borrar/reconstruir índice sin afectar informes.

## R13. Pruebas y verificación visual

**Decisión**:

- unit: métricas, denominadores, alias, hash canónico, redacción, claves de idempotencia, máquina de
  estados.
- contract: rutas, códigos, formularios, validación de confirmación.
- integration: generación con SQLite temporal, renderizado real de gráficas y PDF, reinicio y
  recuperación, doble de Telegram.
- acceptance: recorrido A, B y C con dobles.
- visual: Playwright captura el HTML de impresión; pypdf verifica 2–3 páginas, texto por página y
  objetos embebidos. La revisión visual humana queda documentada en `quickstart.md`.

**Razón**: cubre concordancia, privacidad, duplicados, aislamiento, reinicio y parciales sin envíos
reales.

## R14. Títulos y conclusiones de gráficas

**Decisión**: cada gráfica lleva un título-conclusión determinista generado desde el dataset (por
ejemplo, «El 62 % de los registros pendientes es de severidad 3 o superior»), no una frase fija ni
generada por IA. La tabla alternativa repite los mismos valores y el denominador.

**Razón**: la conclusión cambia con los datos y debe ser reproducible y auditable.

## R15. Independencia de cortes

**Decisión**: A no depende de B/C; B no depende de C. Las tablas de eventos, componentes, intentos y
el ejecutor manual viven en B. C añade reglas y evaluación y reutiliza esa infraestructura. Cada corte
tiene su propia migración aditiva y su verificación de cierre.

**Razón**: permite implementar y aceptar A y B sin esperar C, y evita que una tabla futura bloquee la
verificación de un corte anterior.

## R16. Controles y recuperación del informe

**Decisión**: la síntesis reutiliza autorización por alcance, procedencia (`private_qualys` /
`synthetic_public`), presupuesto con reserva, contexto del proveedor y concurrencia de 005. Qualys
privado no se envía a externos. La generación usa `report_versions.status`, área temporal y
publicación solo de versiones `ready`; un fallo limpia solo su propia versión y la misma
`generation_key` puede reutilizarse sin sobrescribir versiones válidas.

**Razón**: una autorización genérica o una transacción larga no acreditan saldo, contenido permitido
ni recuperación segura.
