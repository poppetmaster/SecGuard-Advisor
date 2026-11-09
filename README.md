# SecGuard Advisor

[![Python](https://img.shields.io/badge/python-3.14.6-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Agente consultor defensivo para ciberseguridad empresarial y seguridad de aplicaciones de IA.
Analiza documentación, contexto organizacional y hallazgos técnicos, identifica brechas y prepara
recomendaciones respaldadas por evidencia, con supervisión humana.

## Tabla de contenidos

- [Propósito](#propósito)
- [Estado del proyecto](#estado-del-proyecto)
- [Funcionalidades](#funcionalidades)
- [Arquitectura](#arquitectura)
- [Stack](#stack)
- [Requisitos](#requisitos)
- [Instalación](#instalación)
- [Configuración](#configuración)
- [Ejecución](#ejecución)
- [Base de datos](#base-de-datos)
- [Corpus y documentos](#corpus-y-documentos)
- [Pruebas](#pruebas)
- [Estructura](#estructura)
- [Calidad y CI](#calidad-y-ci)
- [Documentación](#documentación)
- [Contribución](#contribución)
- [Licencia](#licencia)

## Propósito

SecGuard Advisor ayuda a responsables de TI y seguridad a convertir documentación oficial, contexto
organizacional y hallazgos técnicos en recomendaciones trazables. No ejecuta remediaciones, no
aprueba informes y no certifica cumplimiento: propone y fundamenta, y la decisión queda en manos de
una persona.

## Estado del proyecto

**Funcionalidad 001 implementada y validada localmente.** El repositorio contiene los cortes
T001–T095: base técnica, US1 (casos), US2 (documentos, corpus e índice), US3 (consulta con citas y
revisión humana), US4 (memoria por caso y navegación), US5 (herramienta de hallazgos sintéticos) y
US6 (evidencia de ejecución, límites y trazas). La aceptación local está documentada en
[`docs/evidencia/demo-001.md`](docs/evidencia/demo-001.md). Quedan pendientes las verificaciones
humanas de SC-001 (cronometraje) y SC-003 (diez revisiones), y la revisión en otros navegadores.

### Implementado

- Estructura del paquete con src-layout y `uv_build`.
- Configuración de Ruff, pytest, pre-commit y Makefile.
- Recursos de interfaz locales: CSS compilado con Tailwind, HTMX y Flowbite vendorizados.
- Configuración tipada con secretos protegidos.
- SQLite con 16 tablas, restricciones e índices, y migraciones con Alembic.
- Alcance por caso y reconciliación de estado al arrancar.
- Fábrica FastAPI, `/healthz`, manejo de errores y plantillas base.
- Unidad de trabajo de transacción corta.
- Dataset sintético determinista e idempotente para la demostración.
- Ciclo de vida mínimo de las ejecuciones.
- **US1: creación, listado, detalle y recuperación de casos con contexto, activos, campos
  desconocidos explícitos y persistencia tras reiniciar.**
- **US2: carga de PDF textual y Markdown, validación, extracción, estados, deduplicación,
  versiones, fragmentos localizables, embeddings locales e índice Chroma; adquisición e ingesta
  del corpus público con manifiesto verificable.**
- **US3: consulta documental en español con recuperación fusionada del corpus público y del caso,
  respuestas estructuradas, control automático de citas, abstención ante evidencia insuficiente,
  reintento de turnos fallidos, permiso global de generación y revisión humana del respaldo
  semántico.**
- **US4: conversación con memoria por caso en checkpoints separados, reconciliada antes de cada
  turno, y navegación multipágina con barra lateral persistente y menú móvil.**
- **US5: herramienta `findings_query` acotada al caso, con filtros, conteos calculados en SQLite,
  procedencia sintética y presentación en la consulta documental.**
- **US6: evidencia de ejecución con intentos, pasos, fuentes, herramientas, presupuesto, citas y
  controles separados; límites de operaciones y tiempos; traza externa con estados `disabled`,
  `submitted`, `confirmed` y `failed`, y degradación local cuando LangSmith no está disponible.**
- **Aceptación local: recorrido con dobles y recorrido real con Ollama, corpus, hallazgos,
  reinicio y aislamiento; confirmación de traza por API de lectura con identidad declarada.**
- Pruebas rápidas y fixtures.
- Gobernanza de GitHub: plantillas, labels, Dependabot y workflow de CI.
- Documentación normativa y de planificación.

### Previsto

- Incrementos posteriores (CSV de Qualys, clasificación, entrenamiento o exportaciones) fuera del
  alcance autorizado del primer incremento.

El detalle está en [la especificación](specs/001-consulta-documental/spec.md) y en
[las tareas](specs/001-consulta-documental/tasks.md).

## Funcionalidades

La funcionalidad 001 se construye por incrementos verificables. El producto final permitirá:

1. **Implementado:** crear un caso con contexto educativo y reabrirlo tras reiniciar.
2. **Implementado:** cargar PDF textuales y Markdown, conocer su estado y versiones; el corpus
   público se adquiere e ingesta por separado.
3. **Implementado:** preguntar en español y recibir respuestas con citas localizables, con
   abstención explícita cuando la evidencia no alcanza.
4. **Implementado:** continuar la conversación con memoria separada por caso.
5. **Implementado:** consultar hallazgos sintéticos mediante una herramienta acotada al caso.
6. **Parcial:** la ejecución muestra modelo, digest, parámetros, duración, pasos, fuentes,
   invocaciones de herramienta, presupuesto, citas y traza real con sus estados; la confirmación de
   la traza durante la aceptación y el recorrido completo quedan pendientes.

La creación de casos, la ingesta documental, la consulta con citas, la memoria por caso, la
herramienta de hallazgos y la evidencia de ejecución con trazas están implementadas. La confirmación
de la traza y el recorrido de aceptación siguen pendientes.

## Arquitectura

Monolito modular en un solo proceso. La interfaz y el dominio se separan por paquetes; SQLite
conserva el estado y la procedencia, y Chroma es un índice derivado y reconstruible.

```text
FastAPI + Jinja2 + HTMX
        │
        ├── casos
        ├── documentos e ingesta
        ├── recuperación
        ├── conversación y grafo
        ├── herramientas de hallazgos
        ├── evidencia de ejecución
        └── persistencia
                 │
        SQLite + Chroma + Ollama + LangSmith
```

La constitución completa las decisiones de arquitectura, seguridad y calidad:
[`CONSTITUTION.md`](CONSTITUTION.md).

## Stack

- Python 3.14.6 y `uv`.
- FastAPI, Jinja2 y HTMX.
- Tailwind CSS y Flowbite (gratuito), servidos localmente.
- LangChain y LangGraph.
- Ollama para inferencia local.
- SQLite para estado y procedencia; Chroma para el índice vectorial.
- LangSmith para trazas y evaluación.
- pytest, Ruff, pre-commit, Makefile y GitHub Actions.

## Requisitos

- Python 3.14.6.
- `uv`.
- Node.js 26.11.1, fijado en `.nvmrc`, y npm, solo para compilar CSS y copiar recursos.
- Ollama y los modelos, solo para las pruebas de integración y la futura ejecución del agente.

## Instalación

```bash
uv sync --locked
npm ci
uv run pre-commit install
```

O en un solo paso:

```bash
make install
```

## Configuración

Copia `.env.example` a `.env` y ajusta los valores. `.env` está ignorado por Git.

| Variable | Uso |
|---|---|
| `APP_ENV` | Entorno de ejecución |
| `OLLAMA_BASE_URL` | Endpoint local de Ollama |
| `OLLAMA_MODEL` | Modelo generativo |
| `OLLAMA_EMBEDDING_MODEL` | Modelo de embeddings |
| `SECGUARD_STORAGE_DIR` | Directorio de SQLite, Chroma y originales |
| `SECGUARD_REVIEWER_NAME` | Identidad local declarada para la revisión humana; no es autenticación |
| `SECGUARD_GENERATION_QUEUE_TIMEOUT_SECONDS` | Espera máxima del turno global de generación, en segundos |
| `LANGSMITH_*` | Trazas. Sin clave, la traza queda deshabilitada |

Nunca se versionan secretos ni se muestran en registros o respuestas.

## Ejecución

`make dev` arranca la aplicación en `127.0.0.1` con **un solo worker**. Expone `/healthz`,
casos, documentos, conversación y evidencia de ejecución.

```bash
make dev            # servidor con casos, documentos y consulta
make corpus         # descarga y verifica el corpus oficial
make corpus-ingest  # ingesta el corpus verificado en SQLite y Chroma
make seed-demo      # carga el dataset sintético; requiere el esquema migrado
make demo           # prepara storage/demo, siembra el caso sintético y arranca el servidor
```

### Navegación

La interfaz usa una cabecera fija con la marca y la leyenda «Escenario educativo», una barra lateral
persistente en escritorio y un menú lateral desplegable en móvil. Cada sección es una página GET
propia, accesible por URL y con su ruta de navegación visible:

| Ruta | Sección |
|---|---|
| `/cases` | Casos |
| `/cases/new` | Nuevo caso |
| `/cases/{case_id}` | Resumen del caso (contexto y activos) |
| `/cases/{case_id}/documents` | Documentos (carga, estados, versiones, reintentos) |
| `/cases/{case_id}/chat` | Consulta documental (preguntas, citas, revisión) |
| `/cases/{case_id}/runs/{run_id}` | Evidencia de ejecución, desde cada respuesta |
| `/cases/{case_id}/documents/{document_id}` | Documento con sus versiones y fragmentos |

La cabecera usa el escudo local (`/static/icons/secguard-icon.svg`) junto al nombre y sirve favicon
SVG e ICO desde `/static/icons/`. En pantallas menores a 360 px la insignia «Escenario educativo» se
oculta para no desbordar.

El grupo «Caso abierto» de la barra lateral solo aparece dentro de un caso. Las citas abren el
fragmento correspondiente (del caso o del corpus público) y, cuando vienen de una respuesta, ofrecen
«Volver a la consulta» con un destino construido por el servidor.

### Consulta y revisión humana

1. `uv run alembic upgrade head` y `make corpus && make corpus-ingest`.
2. Con Ollama activo y `qwen3.5:9b` instalado, `make dev`.
3. Creá un caso desde **Nuevo caso** y abrí **Consulta documental** en la barra lateral: la respuesta
   indica si es un borrador, muestra las citas con su control automático y lista los fragmentos
   recuperados en un bloque desplegable, con procedencia y si fueron citados.
4. Exportá `SECGUARD_REVIEWER_NAME="Nombre Apellido"` antes de arrancar si querés registrar la
   revisión humana. Sin esa variable la revisión se rechaza con `409` y no se escribe.
5. Cada cita válida abre el fragmento exacto; la revisión humana es por cita y no adjudica
   prioridades P1–P4 ni aprueba informes.

Los formularios muestran un indicador con texto mientras la solicitud está pendiente, deshabilitan el
envío para evitar duplicados y conservan los valores de texto cuando hay que corregir. Los errores del
servidor (`409`, `429`, `503`, `504`) se muestran dentro del panel afectado. La selección de archivo no
puede restaurarse tras un error: hay que volver a elegirla.

### Memoria de la conversación

Cada caso tiene una sola conversación. El historial visible vive en SQLite y es la fuente
autoritativa; el checkpointer de LangGraph (`storage/checkpoints.sqlite`, `thread_id` =
`conversation_id`) guarda una instantánea operativa que se reconcilia antes de cada turno: si falta
se reconstruye, si quedó adelantado se recorta y si pertenece a otra conversación se reemplaza. No hay
atomicidad entre ambas bases.

El prompt recibe los últimos turnos completos (máximo 8 mensajes y 6000 caracteres) como contexto para
interpretar referencias, nunca como evidencia: las citas se validan solo contra los fragmentos
recuperados en el turno actual. La recuperación de cada pregunta se amplía con la última pregunta
confirmada para interpretar seguimientos.

Antes de cada generación —incluida la reparación de citas— se mide el prompt completo con el
**tokenizador del propio modelo**: vocabulario y fusiones BPE leídos del GGUF instalado por Ollama, con
la plantilla de conversación del renderizador. Se incluyen instrucciones, pregunta, historial, fuentes,
envoltorio, la salida reservada (`num_predict=1200`) y un margen de 320 tokens para variaciones de
plantilla. Si no cabe, se quita primero el historial más antiguo por turnos completos y después las
fuentes de menor rango; la pregunta y los textos incluidos no se recortan y el historial persistido no
se altera. Si el contenido mínimo no cabe, la ejecución falla con `context_budget_exceeded` sin
invocar al modelo; si el tokenizador no está disponible, falla con `context_budget_unavailable` (503)
en lugar de estimar.

Reiniciar la aplicación no pierde mensajes confirmados ni genera respuestas: el historial se lee de
SQLite y los reintentos reutilizan la pregunta original.

El umbral de recuperación (`retrieval_min_score`, 0,35 por defecto) filtra candidatos débiles con
datos de humo; no demuestra que no exista evidencia.

### Hallazgos sintéticos

`make seed-demo` carga el dataset educativo determinista: 12 hallazgos sobre 3 activos, con nombre,
versión y checksum de procedencia. En **Consulta documental** podés preguntar, por ejemplo, «¿Cuántos
hallazgos de severidad High están registrados en este caso? Agrúpalos por activo».

El modelo decide si necesita `findings_query` mediante una llamada estructurada propia y aporta los
argumentos; no hay preguntas codificadas. La herramienta fija el caso en el servidor (`case_id` no es
argumento ni aparece en el resultado), acepta `asset`, `severity`, `qid`, `cve`, `group_by`, `detail` y
`limit`, y calcula totales y grupos en SQLite sobre exactamente los filtros aplicados. El límite afecta
solo al detalle y `truncated` avisa cuando se recortó. Un hallazgo con varios CVE no multiplica filas.

El resultado se muestra con la etiqueta «Datos educativos sintéticos», los filtros aplicados, el total,
las agrupaciones, la procedencia del dataset y el aviso de que no es una importación de Qualys. Un caso
sin hallazgos devuelve total 0 y advierte que eso no demuestra ausencia de vulnerabilidades ni riesgo
bajo. Cada invocación queda registrada en la evidencia de ejecución.

### Evidencia de ejecución y trazas

Cada respuesta enlaza «Ver ejecución». La página muestra el estado y resultado, la duración, el
intento y su vínculo con el anterior, el modelo con digest y parámetros, la versión del prompt, los
pasos con su origen, las fuentes recuperadas, las herramientas con sus argumentos validados y
resúmenes históricos, el presupuesto de contexto medido, las citas con el control automático y la
revisión humana por separado, y el error cuando existe.

El detalle de una herramienta con `detail=true` no se persiste: si la página lo recalcula, se rotula
como una consulta actual y no como el detalle histórico. Los totales y grupos sí son el resultado
registrado.

Con `LANGSMITH_TRACING=true` y `LANGSMITH_API_KEY`, cada turno envía una traza con la ejecución y sus
operaciones relevantes (decisión de herramienta, generación, reparación y llamadas de herramienta).
El estado puede ser `disabled` (sin configuración), `submitted` (envío sin error observado; no
verificado), `confirmed` (verificado por lectura externa) o `failed` (envío no disponible). La
aplicación nunca escribe `confirmed`: eso corresponde a `scripts/confirm_trace.py`, que exige que la
traza exista, pertenezca al proyecto y sus metadatos coincidan con la ejecución local. Si LangSmith no responde, la consulta local se completa
igual y conserva su evidencia. El contenido enviado se limita a metadatos y datos sintéticos; no
incluye la pregunta, prompts, documentos del caso, argumentos de herramienta ni rutas locales.

Límites del turno: 8 operaciones de modelo o herramienta, 2 llamadas a herramientas, 1 reparación,
120 s de turno y 90 s por llamada al modelo. La decisión de herramienta consume tiempo y paso.

## Base de datos

El esquema se crea y evoluciona solo con Alembic. La aplicación no crea tablas al arrancar; al
iniciar reconcilia el estado de las operaciones que quedaron abiertas.

```bash
uv run alembic upgrade head
uv run alembic downgrade base
```

## Corpus y documentos

- `make corpus` descarga las cuatro fuentes oficiales seleccionadas —CSF 2.0 (CSWP 29), AI RMF 1.0
  (AI 100-1), AI 600-1 y OWASP Top 10 for LLM Applications 2025—, verifica título, páginas y
  SHA-256, y escribe `data/corpus/manifest.json`. Una fuente que no coincida se marca `failed` y no
  se reemplaza en silencio.
- `make corpus-ingest` indexa las fuentes verificadas como documentos públicos compartidos.
- La carga del usuario se valida (PDF textual o Markdown y tamaño), se extrae por página o sección,
  se deduplica por hash y se versiona. No hay OCR: un PDF escaneado queda como «sin texto
  utilizable».
- Los originales del corpus viven en `data/corpus/originals/` y no se versionan; el manifiesto sí.

## Pruebas

```bash
make test              # pruebas rápidas, sin integración
make test-integration  # pruebas reales con Ollama y Chroma
make check             # lint + formato + pruebas
```

Estado actual: la base cubre configuración, motor y esquema, alcance, arranque, transacciones,
seed, fixtures, ciclo de vida de ejecuciones, casos, documentos (validación, extracción, fragmentación,
embeddings, índice, versiones, corpus y rutas), conversación con memoria, citas y revisión, la
herramienta de hallazgos (argumentos, filtros, conteos, aislamiento, presupuesto, UI y persistencia) y
la evidencia de ejecución con límites, trazas y redacción de secretos. `make test` incluye la
aceptación con dobles; `make test-integration` ejecuta la aceptación real con Ollama, corpus y
herramienta, además de las integraciones existentes. La confirmación de traza se prueba con dobles y
con una traza real si hay credenciales.

## Aceptación y demo

```bash
make check            # lint, formato y 343 pruebas rápidas
make test-integration # 25 pruebas reales, incluida la aceptación y la traza
make demo             # storage/demo + seed + servidor en 127.0.0.1:8000
```

`make demo` no toca `storage/`. Para la aceptación real se usó un directorio temporal separado con
Ollama, EmbeddingGemma, corpus oficial, caso sintético y `findings_query`. La confirmación de traza se
hace con:

```bash
uv run python scripts/confirm_trace.py --run-id <local> --trace-id <externo> --reviewer "<identidad>"
```

El comando solo escribe `confirmed` después de verificar por API de lectura que la traza existe,
pertenece a `secguard-advisor-dev` y coincide con `run_id`, `case_id` e intento. La evidencia del
recorrido, las cifras, las capturas y la salida de confirmación está en
[`docs/evidencia/demo-001.md`](docs/evidencia/demo-001.md).

## Estructura

```text
src/secguard_advisor/            paquete
├── cases/                       casos y alcance
├── documents/                   documentos, ingesta y embeddings
├── retrieval/                   recuperación, citas y revisión
├── conversation/                grafo, memoria, prompts y concurrencia
├── tools/                       herramienta de hallazgos
├── evidence/                    ejecuciones y trazas
├── web/                         aplicación, rutas, plantillas y estáticos
├── corpus/                      adquisición e ingesta del corpus
└── seed/                        datos sintéticos deterministas

tests/                           unit, contract, integration, acceptance, fixtures
docs/                            planificación, referencias y evidencia
specs/001-consulta-documental/   especificación, plan, investigación, modelo y contratos
.specify/                        Spec Kit y constitución normativa
scripts/                         utilidades de construcción
```

## Calidad y CI

- Ruff para lint y formato.
- pre-commit para higiene, Ruff y sincronización de `uv.lock`.
- pytest para pruebas.
- `make check` como comprobación local completa.
- Workflow de CI en `.github/workflows/ci.yml`, con los mismos comandos que el entorno local.

El workflow está preparado, pero **no se ha ejecutado en GitHub** porque el repositorio remoto aún
no está definido. No se declara un estado de CI que no haya ocurrido.

## Documentación

- [Constitución](CONSTITUTION.md) — fuente normativa única.
- [Especificación](specs/001-consulta-documental/spec.md) — comportamiento y criterios.
- [Plan técnico](specs/001-consulta-documental/plan.md) — arquitectura y decisiones.
- [Modelo de datos](specs/001-consulta-documental/data-model.md) — entidades e invariantes.
- [Contratos](specs/001-consulta-documental/contracts/) — rutas, herramienta, citas y corpus.
- [Quickstart](specs/001-consulta-documental/quickstart.md) — recorrido de validación.
- [Tareas](specs/001-consulta-documental/tasks.md) — plan de implementación.

## Limitaciones conocidas

- **Cuatro vulnerabilidades bajas de npm** en la cadena de construcción de Flowbite:
  `flowbite` → `flowbite-datepicker` → `@rollup/plugin-node-resolve` → `deepmerge`. Son
  dependencias de desarrollo, no del servidor. `npm audit fix` no ofrece una corrección compatible;
  la única sugerida degrada Flowbite a 2.3.0 y se considera un cambio mayor. Se mantiene como
  pendiente explícito y no se usa `npm audit fix --force`.
- La aplicación implementa US1–US6 y T088–T095. Quedan pendientes las verificaciones humanas de
  SC-001 (recorrido cronometrado por una persona) y SC-003 (diez afirmaciones normativas revisadas),
  además de la revisión en navegadores distintos de Chrome/Chromium. La aceptación automatizada y la
  confirmación de traza están documentadas en `docs/evidencia/demo-001.md`.
- `submitted` significa «envío sin error observado», no «traza verificada». La confirmación por API de
  lectura se ejecutó y quedó registrada con la identidad declarada de prueba; no es autenticación.
- El detalle de herramienta no se persiste; cuando la página lo recalcula, se identifica como
  consulta actual. Los conteos sí son históricos.
- La selección de herramienta usa una llamada estructurada adicional (`ToolDecision`) porque Ollama
  no emite `tool_calls` nativos junto con `format`; cuesta una llamada corta al modelo por turno y se
  mide con el mismo tokenizador antes de ejecutarse.
- No hay OCR: los PDF escaneados se reportan como «sin texto utilizable».
- El umbral de recuperación está calibrado con datos de humo; una pregunta sin candidatos no
  demuestra por sí sola que la evidencia no exista.
- La revisión humana del respaldo semántico es por cita y requiere `SECGUARD_REVIEWER_NAME`; es una
  identidad local declarada, no autenticación.
- La revisión visual del ajuste de experiencia se hizo con Playwright sobre Chrome; el recorrido
  completo de aceptación (US6) y la verificación en otros navegadores siguen pendientes.

## Contribución

Lee [`CONTRIBUTING.md`](CONTRIBUTING.md) y [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). Los cambios
arquitectónicos, tecnológicos o de proceso actualizan la constitución en el mismo commit.

## Licencia

[MIT](LICENSE).
