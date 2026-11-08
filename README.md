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

**Funcionalidad 001 en construcción.** El repositorio contiene los cortes T001–T051: base técnica,
US1 (casos) y US2 (documentos, corpus e índice). Las historias de consulta, memoria y hallazgos
siguen pendientes.

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
- Pruebas rápidas y fixtures.
- Gobernanza de GitHub: plantillas, labels, Dependabot y workflow de CI.
- Documentación normativa y de planificación.

### Previsto

- Casos con contexto y activos.
- Ingesta de PDF textual y Markdown con procedencia, deduplicación y versiones.
- Recuperación con citas localizables y abstención ante falta de evidencia.
- Conversación con memoria persistente por caso.
- Herramienta de lectura de hallazgos sintéticos.
- Evidencia de ejecución y trazas reales con LangSmith.
- Revisión humana del respaldo semántico de las citas.

El detalle está en [la especificación](specs/001-consulta-documental/spec.md) y en
[las tareas](specs/001-consulta-documental/tasks.md).

## Funcionalidades

La funcionalidad 001 se construye por incrementos verificables. El producto final permitirá:

1. **Implementado:** crear un caso con contexto educativo y reabrirlo tras reiniciar.
2. **Implementado:** cargar PDF textuales y Markdown, conocer su estado y versiones; el corpus
   público se adquiere e ingesta por separado.
3. **Previsto:** preguntar en español y recibir respuestas con citas localizables.
4. **Previsto:** continuar la conversación con memoria separada por caso.
5. **Previsto:** consultar hallazgos sintéticos mediante una herramienta acotada al caso.
6. **Previsto:** revisar la evidencia de ejecución, las herramientas usadas y la traza.

La creación y consulta de casos y la ingesta documental están implementadas. Las capacidades 3 a 6
siguen pendientes.

## Arquitectura

Monolito modular en un solo proceso. La interfaz y el dominio se separan por paquetes; SQLite
conserva el estado y la procedencia, y Chroma será un índice derivado y reconstruible.

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

`make dev` arranca la base de la aplicación en `127.0.0.1` con **un solo worker**. Expone
`/healthz`, `/cases` y `/cases/new`; la ingesta, el RAG y el agente todavía no existen.

```bash
make dev            # servidor base con casos y documentos
make corpus         # descarga y verifica el corpus oficial
make corpus-ingest  # ingesta el corpus verificado en SQLite y Chroma
make seed-demo      # carga el dataset sintético; requiere el esquema migrado
make demo           # no implementado: requiere el recorrido de consulta (US3+)
```

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
seed, fixtures, ciclo de vida de ejecuciones, casos y documentos (validación, extracción,
fragmentación, embeddings, índice, versiones, corpus y rutas). Las pruebas de integración se
ejecutan con `make test-integration` y requieren Ollama con el modelo de embeddings.

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
- La aplicación implementa US1 (casos) y US2 (documentos, corpus e índice); el RAG, la consulta
  generativa, la conversación, las herramientas y la revisión humana siguen sin implementar. `demo`
  sigue sin implementar.
- No hay OCR: los PDF escaneados se reportan como «sin texto utilizable».

## Contribución

Lee [`CONTRIBUTING.md`](CONTRIBUTING.md) y [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). Los cambios
arquitectónicos, tecnológicos o de proceso actualizan la constitución en el mismo commit.

## Licencia

[MIT](LICENSE).
