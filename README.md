# SecGuard Advisor · Agente de Ciberseguridad

**Proyecto final · Universidad Icesi**  
Cristian Camilo Quebrada · Rubén Darío Sabogal · Edwin Pérez L.

[![Python](https://img.shields.io/badge/python-3.14.6-blue)](https://www.python.org/)
[![uv](https://img.shields.io/badge/uv-0.13.0-5C4EE5)](https://docs.astral.sh/uv/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.162.2-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LangChain](https://img.shields.io/badge/LangChain-1.4.9-1C3C3C?logo=langchain&logoColor=white)](https://python.langchain.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.2.20-1C3C3C)](https://langchain-ai.github.io/langgraph/)
[![Ollama](https://img.shields.io/badge/Ollama-local-black)](https://ollama.com/)
[![SQLite](https://img.shields.io/badge/SQLite-3-003B57?logo=sqlite&logoColor=white)](https://sqlite.org/)
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

SecGuard Advisor se encuentra en **estado funcional local, orientado a demostración y validación
académica**. No es un servicio en producción, no certifica cumplimiento y no sustituye la decisión
humana. El escenario de demostración es educativo y no está ligado a una empresa real.

### Capacidades disponibles

| Capacidad | Qué permite | Estado |
|---|---|---|
| Gestión de casos | Crear, listar, consultar y recuperar casos con contexto, activos y campos desconocidos explícitos | Disponible localmente |
| Consulta documental | Cargar PDF textual y Markdown, conservar versiones y fragmentos, y consultar el corpus público | Disponible localmente |
| Respuestas con evidencia | Responder en español con citas literales, abrir el fragmento fuente y abstenerse si la evidencia no alcanza | Disponible localmente |
| Memoria por caso | Mantener continuidad conversacional con checkpoints separados y reconciliación antes de cada turno | Disponible localmente |
| Hallazgos sintéticos | Consultar el dataset educativo con `findings_query` y conteos calculados en SQLite | Disponible localmente |
| Vulnerabilidades Qualys | Importar CSV validado, revisar una vista previa, confirmar instantáneas, filtrar y consultar registros | Disponible localmente |
| Evidencia de ejecución | Consultar modelo, configuración, pasos, fuentes, herramientas, duración, presupuesto y citas | Disponible localmente |
| Trazabilidad externa | Enviar trazas acotadas a LangSmith y confirmarlas por lectura externa | Disponible; LangSmith es opcional |
| Revisión humana de citas | Registrar respaldo semántico por cita con identidad declarada | Disponible; SC-003 pendiente |
| Privacidad y separación | Mantener datos del caso, corpus, hallazgos y evidencia en espacios separados | Controles implementados; no es una auditoría externa |

### Evidencia de validación

- Pruebas rápidas: `make check` → **409 passed**, 35 deselected.
- Integraciones: `make test-integration` → **34 passed**, 1 skipped por LangSmith desactivado en esa
  ejecución de aceptación real.
- Aceptación real 002: CSV autorizado de **662 registros**, flujo formulario → validación → vista
  previa → confirmación → consulta, y tres consultas reales con Ollama contrastadas con SQLite.
- Navegador: capturas sintéticas y recorrido con Playwright MCP; consola sin errores y recursos
  locales sin fallos.
- Traza LangSmith: integración verificada con datos sintéticos; una ejecución quedó `submitted` y
  luego `confirmed` por lectura externa.

Evidencia localizable:

- [`docs/evidencia/demo-001.md`](docs/evidencia/demo-001.md)
- [`docs/evidencia/002-corte-5/aceptacion-real.md`](docs/evidencia/002-corte-5/aceptacion-real.md)
- [`specs/001-consulta-documental/spec.md`](specs/001-consulta-documental/spec.md)
- [`specs/002-qualys-findings-import/spec.md`](specs/002-qualys-findings-import/spec.md)

### Pendiente y límites

- La funcionalidad 003 —política P1–P4 y formulario de revisión— está **suspendida** y no se presenta
  como disponible.
- Clasificador, entrenamiento, reentrenamiento, MLflow, Prefect, promoción, rollback, exportación y
  empaquetado operativo siguen fuera de este alcance.
- SC-001 (recorrido humano cronometrado) y SC-003 (diez revisiones semánticas) son validaciones
  recomendadas y no bloqueantes; no se ejecutaron.
- La CI remota no se verificó y no se declara en verde.
- La revisión en navegadores distintos de Chromium sigue pendiente.
- El repositorio es público. La rama `main` está protegida contra force push y eliminación. Los
  colaboradores pueden contribuir mediante fork y pull request, o ser invitados como colaboradores
  con permisos de escritura.

## Funcionalidades

El producto ofrece las siguientes capacidades:

1. **Implementado:** crear un caso con contexto educativo y reabrirlo tras reiniciar.
2. **Implementado:** cargar PDF textuales y Markdown, conocer su estado y versiones; el corpus
   público se adquiere e ingesta por separado.
3. **Implementado:** preguntar en español y recibir respuestas con citas localizables, con
   abstención explícita cuando la evidencia no alcanza.
4. **Implementado:** continuar la conversación con memoria separada por caso.
5. **Implementado:** consultar hallazgos sintéticos mediante una herramienta acotada al caso.
6. **Implementado:** la ejecución muestra modelo, digest, parámetros, duración, pasos, fuentes,
   invocaciones de herramienta, presupuesto, citas y traza real con sus estados. SC-001 y SC-003 son
   validaciones recomendadas y no bloqueantes, no ejecutadas.
7. **Implementado:** sección «Vulnerabilidades» con carga del CSV Qualys,
   validación, vista previa, confirmación, cancelación, historial, selector de instantáneas, filtros
   por estado, severidad, prioridad e indicadores, y consulta mediante `findings_query` con
   instantánea fija por turno. La aceptación real local, la privacidad con señuelos, la evidencia
   histórica y la verificación de no-RAG están ejecutadas; SC-001, SC-003 y la CI remota no.

La creación de casos, la ingesta documental, la consulta con citas, la memoria por caso, la
herramienta de hallazgos y la evidencia de ejecución con trazas están implementadas. La confirmación
de traza por API se ejecutó; SC-001 y SC-003 quedan como validaciones recomendadas, no como bloqueos.

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
| `SECGUARD_QUALYS_MAX_BYTES` | Límite de bytes del CSV Qualys; por defecto 10 MiB |
| `SECGUARD_QUALYS_MAX_ROWS` | Límite de filas del CSV Qualys; por defecto 10.000 |
| `SECGUARD_QUALYS_MAX_FIELD_CHARS` | Límite de caracteres por campo; por defecto 20.000 |
| `SECGUARD_QUALYS_MAX_CVES` | Límite de CVE por registro; por defecto 1.000 |
| `SECGUARD_QUALYS_STAGING_TTL_SECONDS` | Vigencia del staging/rechazo; por defecto 24 h |
| `LANGSMITH_*` | Trazas. Sin clave, la traza queda deshabilitada. La instancia local de demo tiene `LANGSMITH_TRACING=true`; `.env.example` mantiene `false` para evitar envíos accidentales |

Nunca se versionan secretos ni se muestran en registros o respuestas.

## Ejecución

`make dev` arranca la aplicación en `127.0.0.1` con **un solo worker**. Expone `/healthz`,
casos, documentos, conversación y evidencia de ejecución.

```bash
make dev             # servidor con casos, documentos y consulta
make corpus          # descarga y verifica el corpus oficial
make corpus-ingest   # ingesta el corpus verificado en el almacenamiento configurado
make seed-demo       # carga el dataset sintético en el almacenamiento configurado
make demo-prepare    # storage/demo: migraciones + corpus + dataset sintético
make demo            # ejecuta demo-prepare y arranca storage/demo
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
| `/cases/{case_id}/vulnerabilities` | Vulnerabilidades: formulario, preview, confirmación y snapshot |
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

El resultado sintético se muestra con la etiqueta «Datos educativos sintéticos», los filtros
aplicados, el total, las agrupaciones, la procedencia del dataset y el aviso de que no es una
importación de Qualys. La importación Qualys confirmada se consulta desde la sección
«Vulnerabilidades» y mediante `findings_query` con origen importado; no se mezcla con las etiquetas
sintéticas. Un caso sin hallazgos devuelve total 0 y advierte que eso no demuestra ausencia de
vulnerabilidades ni riesgo bajo. Cada invocación queda registrada en la evidencia de ejecución.

### Vulnerabilidades Qualys (US1–US3)

La sección **Vulnerabilidades** del caso permite cargar el CSV filtrado de Qualys, validarlo y revisar
la vista previa antes de confirmar. La validación local aplica severidad 1–5, estados admitidos con
revisión manual para desconocidos, evaluación separada de explotabilidad y malware, prioridad conjunta
solo con ambos positivos, rechazo completo y snapshots independientes. También compara el manifiesto
local y calcula posibles repeticiones sin deduplicar.

El formulario recibe únicamente el CSV. Tras confirmar, la instantánea queda consultable desde la
sección y mediante `findings_query`, que usa por defecto la última instantánea confirmada, distingue
origen e identificador de instantánea y no mezcla datos sintéticos con importados. El historial y el
selector permiten consultar una instantánea anterior; la selección se conserva en la URL y el
resultado muestra siempre la instantánea usada. La primera consulta de un turno fija el snapshot y
otra solicitud en el mismo turno devuelve `snapshot_locked`. Las instantáneas no se suman y la
ausencia de un registro no se interpreta como remediación.

La tabla y la consulta comparten los mismos filtros: grupo de estado (`pending_known`, `fixed`,
`manual_review`, `all`), nivel de severidad 1–5, prioridad conjunta, explotabilidad, malware, activo,
QID y CVE. Los estados importados se agrupan en pendientes conocidos (`Active`, `New`, `Re-Opened`),
`Fixed` y revisión manual para estados desconocidos; un estado desconocido no es un indicador
indeterminado. La severidad conserva el valor original y se presenta con la escala del proyecto
(1 Informativa … 5 Crítica), sin equipararla con CVSS, QDS, TruRisk ni prioridades P1–P4.

Explotabilidad y malware se muestran como distribuciones independientes (positivo, negativo/no
informado e indeterminado) y la prioridad conjunta solo se marca cuando ambos son positivos; un único
indicador positivo no crea prioridad. `Fixed` con ambos positivos es un antecedente prioritario, no
una remediación pendiente. Cada motivo se expresa con texto, no solo con color.

En `findings_query`, `origin=imported` usa `pending_known` por defecto, mientras que `origin=all` usa
`all` y devuelve bloques separados por origen. `origin=all` solo admite `status_group=all`;
`status_group` con `origin=synthetic`, y `snapshot_id`, `priority`, `exploitability` o `malware` con
un origen distinto de `imported`, se rechazan con un error explícito. Los conteos se calculan en
SQLite sin multiplicar por CVE y el límite de detalle no reduce los totales.

Al aplicar o limpiar filtros, la sección conserva la importación seleccionada y los parámetros
reproducibles en la URL, muestra los filtros activos y nunca cambia en silencio a la última
instantánea. Los estados vacíos distinguen «Sin importaciones confirmadas» de «Sin registros para
estos filtros»; ninguno afirma ausencia de vulnerabilidades ni riesgo bajo.

El agregado `manual_review_rows` se presenta como «Registros que requieren revisión de estado o
indicadores»: cuenta una vez los registros con estado desconocido, explotabilidad indeterminada o
malware indeterminado. No es la suma de esas categorías y no cambia el grupo `manual_review`, que
sigue reservado a estados desconocidos.

La evidencia de ejecución conserva el resumen histórico y recalcula el detalle sobre el `snapshot_id`
registrado, no sobre «la última»; muestra la instantánea utilizada y la etiqueta «Consulta actual».
La importación no crea documentos, fragmentos, vectores ni citas del RAG. Las pruebas de privacidad
inspeccionan trazas, prompts, callbacks, memoria, errores y HTML con señuelos sintéticos; no usan
`LANGSMITH_TRACING=false` como única prueba.

El CSV real se usa solo en comprobaciones locales con almacenamiento temporal; no se versiona ni se
envía a servicios externos. La aceptación real T039 se ejecutó localmente: 662 registros, 631 Active,
10 New, 21 Re-Opened, severidades 1=20/2=316/3=94/4=162/5=70, explotabilidad 129 positivas y 533
indeterminadas, malware 8 positivos y 654 indeterminados, 8 ambos positivos, 179 registros con varios
CVE, 10 grupos de posibles repeticiones y 11 filas adicionales. Capturas sintéticas de la UI:
[`docs/evidencia/002-corte-2/`](docs/evidencia/002-corte-2/),
[`docs/evidencia/002-corte-3/`](docs/evidencia/002-corte-3/) y
[`docs/evidencia/002-corte-5/`](docs/evidencia/002-corte-5/).

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
operaciones relevantes (alcance, memoria, recuperación, decisión de herramienta, generación,
validación, reparación, herramienta y persistencia). Además del resultado, envía metadatos seguros:
versión de la aplicación, entorno, modelo y digest del generador, modelo y dimensión de embeddings,
contexto y parámetros de generación, límites, presupuesto de contexto, cantidad de fuentes y orígenes,
duración por paso, conteos de claims, citas y recomendaciones, códigos de rechazo de citas, y
agregados de `findings_query` (total, estado, severidad, indicadores y prioridad conjunta). No envía
la pregunta, prompts, documentos, citas literales, argumentos de herramienta, filas, claves ni rutas
locales.

El estado puede ser `disabled` (sin configuración), `submitted` (envío sin error observado; no
verificado), `confirmed` (verificado por lectura externa) o `failed` (envío no disponible). La
aplicación nunca escribe `confirmed`: eso corresponde a `scripts/confirm_trace.py`, que exige que la
traza exista, pertenezca al proyecto y sus metadatos coincidan con la ejecución local. Si LangSmith no
responde, la consulta local se completa igual y conserva su evidencia.

Límites del turno: 8 operaciones de modelo o herramienta, 2 llamadas a herramientas, 1 reparación,
120 s de turno y 90 s por llamada al modelo. La decisión de herramienta consume tiempo y paso.

## Base de datos

El esquema se crea y evoluciona solo con Alembic. La aplicación no crea tablas al arrancar; al
iniciar reconcilia el estado de las operaciones que quedaron abiertas. El esquema actual tiene 20
tablas: las 16 de 001 y las cuatro de snapshots Qualys.

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
la evidencia de ejecución con límites, trazas y redacción de secretos, y la funcionalidad 002
(lector, políticas, validación, staging, formulario, rutas, manifiesto, repeticiones, filtros,
privacidad, evidencia histórica y no-RAG). `make test` incluye la aceptación
con dobles; la probe del CSV real está marcada como integración y se omite si los archivos externos no
están disponibles. `make test-integration` ejecuta la aceptación real con Ollama, corpus y herramienta,
además de las integraciones existentes; no es necesaria para la suite rápida. La confirmación de traza
se prueba con dobles y con una traza real si hay credenciales.

## Aceptación y demo

```bash
make check            # lint, formato y 409 pruebas rápidas
make test-integration # 34 pruebas de integración y 1 skipped (LangSmith no configurado)
make demo-prepare     # storage/demo: migraciones + corpus + dataset sintético
make demo             # arranca storage/demo en 127.0.0.1:8000
```

`make demo` no toca `storage/`. `make corpus-ingest` y `make seed-demo` operan sobre el
`SECGUARD_STORAGE_DIR` configurado, no sobre `storage/demo`. Para la aceptación real se usó un
directorio temporal separado con Ollama, EmbeddingGemma, corpus oficial, caso sintético y
`findings_query`; esa base no se copió a `storage/demo`. La confirmación de traza se hace con:

```bash
uv run python scripts/confirm_trace.py --run-id <local> --trace-id <externo> --reviewer "<identidad>"
```

El comando solo escribe `confirmed` después de verificar por API de lectura que la traza existe,
pertenece a `secguard-advisor-dev` y coincide con `run_id`, `case_id` e intento. La traza confirmada
de la aceptación pertenece al entorno temporal de aceptación, no a `storage/demo`; no se copió ninguna
base. La evidencia del recorrido, las cifras, las capturas y la salida de confirmación está en
[`docs/evidencia/demo-001.md`](docs/evidencia/demo-001.md). Los materiales humanos pendientes están
en [`docs/evidencia/sc-001-guia.md`](docs/evidencia/sc-001-guia.md) y
[`docs/evidencia/sc-003-revision.md`](docs/evidencia/sc-003-revision.md).

## Estructura

```text
src/secguard_advisor/            paquete
├── cases/                       casos y alcance
├── documents/                   documentos, ingesta y embeddings
├── retrieval/                   recuperación, citas y revisión
├── conversation/                grafo, memoria, prompts y concurrencia
├── tools/                       herramienta de hallazgos
├── vulnerabilities/             importación y snapshots Qualys
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
- La aplicación implementa US1–US6 y T088–T095. SC-001 (recorrido cronometrado por una persona) y
  SC-003 (diez afirmaciones normativas revisadas) son validaciones recomendadas y no bloqueantes;
  sus resultados reales no se ejecutaron. La revisión en navegadores distintos de Chrome/Chromium
  sigue pendiente. La aceptación automatizada y la confirmación de traza están documentadas en
  `docs/evidencia/demo-001.md`.
- `submitted` significa «envío sin error observado», no «traza verificada». La confirmación por API de
  lectura se ejecutó y quedó registrada con la identidad declarada de prueba; no es autenticación.
- El detalle de herramienta no se persiste; cuando la página lo recalcula usa el `snapshot_id`
  histórico, conserva los filtros, indica la instantánea utilizada y se identifica como «Consulta
  actual». Los conteos sí son históricos.
- La selección de herramienta usa una llamada estructurada adicional (`ToolDecision`) porque Ollama
  no emite `tool_calls` nativos junto con `format`; cuesta una llamada corta al modelo por turno y se
  mide con el mismo tokenizador antes de ejecutarse.
- No hay OCR: los PDF escaneados se reportan como «sin texto utilizable».
- El umbral de recuperación está calibrado con datos de humo; una pregunta sin candidatos no
  demuestra por sí sola que la evidencia no exista.
- La revisión humana del respaldo semántico es por cita y requiere `SECGUARD_REVIEWER_NAME`; es una
  identidad local declarada, no autenticación.
- La revisión visual del ajuste de experiencia se hizo con Playwright sobre Chrome; la verificación
  en otros navegadores sigue pendiente. SC-001 y SC-003 son recomendadas y no bloquean el segundo
  incremento.

## Contribución

Lee [`CONTRIBUTING.md`](CONTRIBUTING.md) y [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). Los cambios
arquitectónicos, tecnológicos o de proceso actualizan la constitución en el mismo commit.

## Licencia

[MIT](LICENSE).
