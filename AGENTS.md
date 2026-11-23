# AGENTS — SecGuard Advisor

Contexto del proyecto para sesiones con asistentes LLM. Está versionado en el repositorio.

## Proyecto

SecGuard Advisor es un agente consultor defensivo para ciberseguridad empresarial. Ayuda a las
empresas a consultar documentos de ciberseguridad, analizar reportes de vulnerabilidades y obtener
respuestas con evidencia verificable para apoyar sus decisiones. Analiza documentación, contexto
organizacional y hallazgos técnicos, identifica brechas y prepara recomendaciones respaldadas por
evidencia, con supervisión humana.

El alcance del análisis puede ser cualquier proceso, servicio, infraestructura, sistema o aplicación.
Puede abordar seguridad de sistemas de IA cuando corresponda al caso, pero no exige que exista una
aplicación de IA y no certifica aplicaciones, empresas ni cumplimiento normativo.

Los artefactos de `specs/001-consulta-documental/` y `docs/evidencia/` documentan el alcance original
y se conservan como registro histórico. La definición vigente es la de este archivo y el README.

**Estado actual**: base técnica, US1–US6 y T088–T095 (cortes T001–T095). La aplicación arranca con
`/healthz`, casos, documentos, consulta documental con citas y revisión humana del respaldo, memoria
por caso en checkpoints separados, la herramienta `findings_query` acotada al caso y la evidencia de
ejecución con intentos, límites y trazas. La aceptación local está documentada en
`docs/evidencia/demo-001.md`. SC-001 (recorrido humano cronometrado) y SC-003 (diez revisiones
semánticas) son validaciones recomendadas y no bloqueantes; no se ejecutaron y no se presentan como
aprobadas. La revisión en otros navegadores sigue pendiente.

**US1–US3 de 002 implementadas**: el módulo `vulnerabilities` procesa el CSV filtrado de Qualys de
forma local con lector, políticas versionadas, validación por fila, staging/rechazo, snapshots
confirmables, comparación de manifiesto y posibles repeticiones. La sección «Vulnerabilidades» incluye
formulario, vista previa, confirmación, cancelación, historial, selector de instantáneas, filtros por
estado, severidad, prioridad e indicadores, y consulta de registros confirmados mediante
`findings_query` (origen, instantánea, estado, severidad, prioridad e indicadores incluidos). La
primera consulta de un turno fija el snapshot y las posteriores lo reutilizan. El corte final añade
privacidad de payloads, evidencia histórica sobre el snapshot persistido, separación del RAG y
aceptación real local con el CSV filtrado y Ollama. SC-001, SC-003 y la CI remota no se ejecutaron.

**003 suspendida temporalmente (2026-11-11):** la política P1–P4 sigue propuesta y no aprobada; la
simulación con el CSV filtrado dio 0/662 registros clasificables y 662 con contexto faltante. No se
retoma 003 hasta completar las mejoras 004–007 (Qdrant, proveedor API, acción operativa y aceptación
integrada), con una estrategia explícita de contexto y etiquetas. La especificación y el checklist se
conservan. Ver
[`docs/planificacion/hoja-ruta-mejoras-profesor.md`](docs/planificacion/hoja-ruta-mejoras-profesor.md).

**Constitución 1.3.0 (ratificación del responsable registrada; acuerdos del equipo no constan):**
fija como arquitectura objetivo Qdrant en servidor local persistente para 004, un proveedor API
explícito para 005 y una acción externa controlada para 006. 004 reconstruye el índice desde cero
desde SQLite, sin migrar vectores de Chroma, sin escritura dual, sin comparación obligatoria y sin
retorno a Chroma; los archivos Chroma existentes no se borran. La implementación actual usa Qdrant +
Ollama; 004 está implementado y aceptado localmente; 005 tiene adaptadores API implementados con
aceptación externa real pendiente; 006 Cortes A y B están implementados localmente, pero el envío
real de Telegram, las reglas automáticas y la recuperación automática no están implementados ni
aceptados.

**005 Entregas 1–3 completadas (2026-11-22):** `specs/005-generador-configurable/` define la
selección explícita del generador entre Ollama local, DeepSeek (`deepseek-flash`) y Anthropic Claude
Haiku (`claude-haiku-5-5`). La página `/settings/ai`, dentro del grupo **Administración**, permite seleccionar proveedor, modelo
y límites no secretos, persistidos en SQLite con precedencia sobre `Settings`/`.env`; cada turno toma una
instantánea y `.env` conserva claves, endpoints y presupuestos. Ollama está operativo; DeepSeek/Anthropic tienen adaptadores, contexto,
costo, presupuesto, autorización por caso, bloqueo de herramientas importadas, redacción y evidencia
de uso. La evaluación real del 2026-11-23 comparó 10 escenarios congelados por proveedor sobre corpus
público y un caso ficticio: Ollama 6/10 aprobados, DeepSeek 6/9 y Anthropic 4/9; S08 quedó bloqueado
en los externos por `external_tool_blocked`. La evidencia está en
`docs/evidencia/005-evaluacion-proveedores/`. No hay fallback ni cambio de proveedor en un turno. Los
externos exigen credencial, presupuesto aprobado y autorización por caso para datos públicos o
ficticios; Qualys y los datos privados no salen. La calidad externa observada no permite declarar
ningún proveedor aceptado en uso real; 005 mantiene **aceptación local parcial** y T039 sigue
pendiente por el marker `external` de pytest. El panel **Uso y comparativos de IA** vive en
`/settings/ai/usage`, dentro de Administración: persiste telemetría por solicitud en `ai_requests`,
importa el informe 005 de forma idempotente con `make import-evaluation` y no invoca modelos al
consultar o filtrar.

**006 Corte A implementado (2026-11-23):** el caso tiene una sección **Informe ejecutivo** que
genera una versión inmutable desde una instantánea Qualys confirmada. El dataset canónico se calcula
en SQLite, se persiste en `report_versions` y alimenta la vista web y el PDF; el PDF se compone con
Playwright/Chrome y gráficas ECharts renderizadas localmente con Node (SSR a SVG). Se mantienen top 5
de activos por defecto, alias de activos, exclusión del título sensible (`include_case_title=false`),
indicadores independientes, `Fixed` separado y ausencia de P1–P4. La síntesis de IA es opcional y cae
a un informe factual si falla o no está autorizada. La síntesis externa exige procedencia
`synthetic_public`, autorización `fictional_case`, presupuesto con reserva y los controles de contexto y
concurrencia de 005; Qualys privado no sale. La recuperación automática futura usa `generation_key`; C
no se implementó. Evidencia: `docs/evidencia/006-corte-a/`.

**006 Corte B implementado (2026-11-23):** los contactos de Telegram se registran en
`/settings/contacts` (grupo **Administración**) con alias e identificador de chat; nunca se piden
teléfono ni correo. Un contacto nuevo queda `unverified`, con consentimiento `pending` y `active=false`.
La verificación envía un código de 6 dígitos, persiste solo su hash, expira en 10 minutos y limita a 3
intentos y 3 solicitudes por ventana. Consentimiento, activación y vínculo por caso son pasos
separados. El envío manual parte de una versión `ready`, construye un manifiesto canónico con versión,
texto saliente, hash del PDF, política y destinatarios enmascarados, y exige una confirmación que se
invalida si cambia el contenido o los destinatarios. El resumen y el PDF son componentes
independientes que revalidan contacto, consentimiento, vínculo y manifiesto antes de cada envío. La
idempotencia es `SHA-256(caso:versión:contacto)` y no depende del modo manual/automático; los estados
son preparado, solicitado, aceptado, fallido, incierto, parcial y omitido, y «aceptado» no equivale a
entregado ni leído. Un timeout incierto no se reintenta automáticamente y el reinicio marca las
solicitudes en vuelo como inciertas conservando los componentes aceptados. El transporte real está
implementado con timeouts y sin reintentos internos, pero toda la aceptación del corte usa el doble
`StubTelegramTransport`: no se enviaron códigos ni informes reales. Evidencia:
`docs/evidencia/006-corte-b/`.

La interfaz es multipágina con renderizado del servidor: cabecera, barra lateral persistente en
escritorio, menú desplegable en móvil y una sección visible por ruta. Las secciones son `/cases`,
`/cases/new`, `/cases/{id}` (resumen), `/cases/{id}/documents`, `/cases/{id}/vulnerabilities`, `/cases/{id}/reports` y
`/cases/{id}/chat`; la evidencia de ejecución vive en `/cases/{id}/runs/{run_id}`. El grupo
**Administración** incluye `/settings/ai`, `/settings/ai/usage` y `/settings/contacts`. Las
notificaciones por caso viven en `/cases/{id}/notifications` y la preparación en
`/cases/{id}/reports/{report_id}/versions/{n}/notifications`. HTMX se conserva solo dentro de cada
sección.

La verdad normativa vive en [`CONSTITUTION.md`](./CONSTITUTION.md), que es un enlace simbólico a
`.specify/memory/constitution.md`. Se edita únicamente el archivo real; nunca se mantienen dos
copias. Ante cualquier cambio arquitectónico, tecnológico o de proceso, actualiza la constitución en
el mismo commit.

## Stack

- Python 3.14.6, `uv`, src-layout, `uv_build`.
- FastAPI, Jinja2, HTMX, Tailwind CSS, Flowbite (gratuito) y Apache ECharts 5.6.0
  (Apache-2.0), recursos locales.
- LangChain, LangGraph, SQLite y LangSmith. Ollama y Qdrant son la implementación actual; Qdrant es
  el único backend documental (004, implementado y aceptado localmente en el Corte 6). Chroma quedó
  retirado del código. Los adaptadores API de 005 existen, pero no tienen aceptación externa real y
  no hay proveedor seleccionado.
- pytest, Ruff, pre-commit, Makefile y GitHub Actions.

## Estructura

```text
src/secguard_advisor/     código del paquete
tests/                    unit, contract, integration, acceptance, fixtures
docs/                     planificación, referencias y evidencia
specs/001-consulta-documental/  spec, plan, research, data-model, contracts, tasks
.specify/                 Spec Kit y constitución normativa
```

## Comandos

```bash
make help               # lista los objetivos
make install            # uv sync --locked + hooks + npm ci
make assets             # compila Tailwind y copia recursos vendorizados
make lint               # Ruff
make format             # Ruff format
make test               # pruebas rápidas, sin integración
make test-integration   # pruebas reales con Ollama y Qdrant
make test-external      # pruebas externas; se omiten sin autorización explícita
make check              # lint + formato + pruebas
make dev                # servidor con casos, documentos y consulta, un worker
make corpus             # descarga y verifica el corpus oficial
make corpus-ingest      # ingesta el corpus verificado
make seed-demo          # dataset sintético; requiere el esquema migrado
make qdrant-up          # infraestructura local de 004; no cambia el backend
make qdrant-down        # detiene Qdrant conservando su volumen
make qdrant-health      # /readyz y versión del servidor Qdrant
make import-evaluation  # importa el informe de evaluación 005; no llama a proveedores
uv run alembic upgrade head  # crea/actualiza el esquema
SECGUARD_REVIEWER_NAME="Nombre" make dev  # habilita la revisión humana declarada
```

`make corpus` y `make corpus-ingest` están implementados y son las vías autorizadas para el corpus.
`make qdrant-up|qdrant-health|qdrant-rebuild` y `uv run python scripts/rebuild_qdrant.py --status`
son la interfaz operativa de Qdrant, el backend documental. Chroma quedó retirado del código y sus
archivos se conservan. El modo embebido de Qdrant se usa solo en pruebas y no sustituye la aceptación
contra el servidor. `make demo-prepare` prepara `storage/demo` y `make demo` lo arranca sin tocar
`storage/`. `seed-demo` requiere el esquema migrado. El esquema se crea y evoluciona solo con Alembic;
la aplicación no ejecuta `create_all` al arrancar.

## Reglas duras

- Toda gestión de dependencias pasa por `uv`. Prohibido `pip` y `requirements.txt`.
- `uv.lock` se versiona. `uv sync --locked` debe reproducir el entorno.
- Ruff para lint y formato; pre-commit instalado; `make check` en verde antes de integrar.
- pytest con patrón AAA. Las pruebas de integración usan Ollama y recuperación reales; los mocks
  solo en pruebas unitarias identificadas.
- Documentación e interfaz en español. Código, identificadores, tablas y comentarios en inglés.
- Conventional Commits. Sin atribución de IA.
- No se versionan secretos, `.env`, `storage/` ni `data/corpus/originals/`.
- No se descarga corpus, no se cargan modelos grandes ni se ejecutan APIs pagadas sin una tarea que
  lo autorice. `make corpus` y `make corpus-ingest` son las vías autorizadas para el corpus.
- Los originales del corpus no se versionan; el manifiesto `data/corpus/manifest.json` sí.
- No hay OCR: un PDF escaneado se reporta como «sin texto utilizable».
- Un solo proceso y un worker. El semáforo global de generación y la reconciliación de arranque lo
  asumen.
- No se publica repositorio, no se hace push ni se despliega nada sin autorización explícita.
- No se modifica la configuración global de Git. La identidad local del repositorio ya está
  definida.
- `SECGUARD_REVIEWER_NAME` es una identidad local declarada para la revisión humana; no es
  autenticación. Sin esa variable no se escribe ninguna revisión.
- El informe ejecutivo solo se genera desde una importación Qualys confirmada. Su dataset y PDF son
  inmutables por versión; la web y el PDF consumen el mismo dataset persistido. No se suman categorías
  solapadas ni se multiplican registros por CVE.
- El PDF se compone localmente con Playwright/Chrome y gráficas ECharts SSR con Node; no se usa CDN.
  La inspección visual del PDF es una comprobación separada de la extracción de texto con pypdf.
- Top 5 de activos es el valor predeterminado y el título sensible del caso está excluido del
  contenido saliente salvo política explícita. La síntesis de IA es opcional y nunca reemplaza el
  informe factual.
- `ai_application` es el nombre histórico del alcance del análisis. Se conserva por compatibilidad y
  se presenta como «Alcance del análisis»; no se renombra la columna, no se agrega un campo nuevo y
  no se reescribe el contenido de casos existentes.
- El historial visible es la fuente autoritativa (`messages`). `storage/checkpoints.sqlite` es
  memoria operativa y se reconcilia antes de cada turno; no hay atomicidad entre bases.
- El historial del prompt se acota a 8 mensajes y 6000 caracteres. El historial no es evidencia:
  las citas se validan contra los fragmentos del turno actual.
- Antes de cada generación se mide el prompt con el tokenizador del modelo (vocabulario y BPE del
  GGUF instalado) y su plantilla, no con el `token_count` de EmbeddingGemma ni con un divisor por
  bytes. Si no cabe, se reduce historial y luego fuentes; si el mínimo no cabe,
  `context_budget_exceeded`; si falta el tokenizador, `context_budget_unavailable` (503).
- El umbral de recuperación es un filtro de candidatos débiles; una recuperación vacía no demuestra
  ausencia de evidencia. El generador configurado es `qwen3.5:9b`, con razonamiento desactivado.
- `findings_query` recibe el alcance por clausura: `case_id` no es argumento ni aparece en el resultado
  expuesto al modelo. Los conteos se calculan en SQLite sobre los filtros aplicados; el límite afecta
  solo al detalle y un CVE con varias relaciones no multiplica filas. La herramienta consulta por
  defecto la última instantánea Qualys confirmada y distingue origen sintético/importado; los
  resultados importados identifican la instantánea y no se mezclan con las etiquetas sintéticas. La
  primera resolución de importación fija el snapshot del turno y otra solicitud devuelve
  `snapshot_locked`. Solo se consultan importaciones `confirmed`, no se envían `Results` al modelo y
  los registros Qualys no se convierten en documentos, vectores ni citas del RAG. Un total 0 no
  demuestra ausencia de vulnerabilidades ni implica remediación.
- La severidad importada usa la escala del proyecto 1 Informativa, 2 Baja, 3 Media, 4 Alta y 5
  Crítica; conserva el valor original y no se equipara con CVSS, QDS, TruRisk ni prioridades P1–P4.
  Los estados se agrupan en `pending_known` (Active, New, Re-Opened), `fixed` y `manual_review`
  (desconocido); un estado desconocido no es un indicador indeterminado. Explotabilidad y malware son
  distribuciones independientes y la prioridad conjunta solo aplica con ambos positivos; `Fixed` con
  ambos positivos es antecedente, no remediación pendiente.
- La tabla y `findings_query` comparten filtros. `origin=imported` usa `pending_known` por defecto;
  `origin=all` usa `all`, devuelve bloques separados y solo admite `status_group=all`. Los filtros
  importados exigen `origin=imported`. La UI conserva la instantánea seleccionada y los parámetros en
  la URL, muestra filtros activos y distingue «Sin importaciones confirmadas» de «Sin registros para
  estos filtros».
- `manual_review_rows` cuenta una vez los registros con estado desconocido, explotabilidad
  indeterminada o malware indeterminado. Se presenta como «Registros que requieren revisión de estado
  o indicadores»; no se suma con las distribuciones y no convierte un estado Active/New/Re-Opened/
  Fixed en revisión manual.
- La evidencia histórica recalcula el detalle solo sobre el `snapshot_id` del resumen persistido y
  conserva los filtros originales; muestra la instantánea usada y «Consulta actual» sin sustituir el
  resumen. La importación no crea documentos, fragmentos, vectores ni citas del RAG. Las trazas
  externas envían metadatos acotados y nunca pregunta, prompts, documentos, argumentos, resultados de
  fila, claves ni rutas locales; `Results` completo no llega al modelo ni a la interfaz.
- La selección de herramienta usa una llamada estructurada `ToolDecision` antes de la respuesta:
  Ollama no emite `tool_calls` nativos junto con `format`. Son como máximo dos ejecuciones por turno y
  la decisión también se mide con el tokenizador del generador.
- Los límites del turno son: 8 operaciones de modelo o herramienta, 2 llamadas a herramientas, 1
  reparación, 120 s de turno y 90 s por llamada al modelo. La decisión de herramienta consume paso y
  tiempo; ninguna llamada recibe un presupuesto nuevo después de otra.
- La página «Ver ejecución» lee solo registros persistidos. Si recalcula el detalle de una herramienta,
  lo rotula como consulta actual; los totales y grupos son históricos. El control automático de citas
  y la revisión humana se muestran por separado.
- `trace_status` solo puede ser `disabled`, `submitted` o `failed` por la aplicación; `submitted` no
  significa verificado. `confirmed` lo escribe únicamente `scripts/confirm_trace.py` tras verificar
  por API de lectura que la traza existe, pertenece al proyecto y coincide con `run_id`, `case_id` e
  intento, registrando identidad declarada, fecha y evidencia. Las trazas envían metadatos acotados:
  nunca pregunta, prompts, documentos del caso, argumentos de herramienta, claves ni rutas locales.
- Las pruebas de aceptación con dobles viven en `tests/acceptance/test_journey.py`; la aceptación real
  con Ollama, corpus y herramienta en `tests/acceptance/test_journey_real.py`, siempre con
  almacenamiento separado (`SECGUARD_ACCEPTANCE_DIR` o `tmp_path`). `make demo-prepare` prepara
  `storage/demo` con migraciones, corpus y seed; `make demo` arranca esa misma instancia. No modifica
  `storage/`.
- El token del bot de Telegram vive solo en `.env` o configuración secreta; nunca en SQLite, HTML,
  capturas, logs ni Git. El transporte predeterminado es el doble `stub`; el transporte real no se usa
  en pruebas ni en aceptación sin autorización explícita y un destino acordado.
- Un contacto nuevo es `unverified`, con consentimiento `pending` y `active=false`; no se piden
  teléfono ni correo. El código de verificación se persiste solo como hash, expira en 10 minutos y
  admite 3 intentos y 3 solicitudes por ventana; nunca se guarda ni se muestra en claro.
- El envío manual exige una versión `ready` y sus artefactos persistidos, y no regenera el informe. El
  manifiesto incluye versión, texto saliente, hash del PDF, política y destinatarios enmascarados; la
  confirmación se invalida si cambia el contenido o los destinatarios.
- Resumen y PDF son componentes independientes; antes de cada uno se revalidan contacto,
  consentimiento, vínculo y manifiesto. La idempotencia es `SHA-256(caso:versión:contacto)` y no
  depende del modo manual/automático. «Aceptado» no equivale a entregado ni leído.
- Un timeout incierto no se reintenta automáticamente y el reinicio conserva los componentes
  aceptados. Ninguna llamada HTTP se ejecuta con una transacción SQLite de escritura abierta.
- No se declaran resultados, métricas ni estados de CI antes de ejecutarlos.

## Spec Kit

El flujo es: constitución → especificación → aclaraciones → plan → tareas → análisis →
implementación por incrementos. Los artefactos activos están en
`specs/001-consulta-documental/`. No se amplía el alcance sin una decisión explícita.

## Búsqueda de código

Si `tgrep` está instalado, úsalo para búsquedas de código en lugar de `grep` o `find`. En OpenCode
la preferencia se aplica mediante `.opencode/rules/tgrep.md`.
