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

**Base técnica en construcción.** Este repositorio contiene los cortes T001–T027: estructura,
tooling, persistencia, configuración, arranque base y datos sintéticos. La funcionalidad 001
todavía no está implementada.

### Implementado en este corte

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

La funcionalidad 001 se construirá por incrementos verificables. El producto final de este
incremento permitirá:

1. Crear un caso con contexto educativo y reabrirlo tras reiniciar.
2. Cargar PDF textuales y Markdown, conocer su estado y distinguir guías públicas de evidencias.
3. Preguntar en español y recibir respuestas con citas localizables.
4. Continuar la conversación con memoria separada por caso.
5. Consultar hallazgos sintéticos mediante una herramienta acotada al caso.
6. Revisar la evidencia de ejecución, las herramientas usadas y la traza.

Ninguna de estas capacidades está implementada todavía.

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
`/healthz` y los recursos estáticos; las rutas de producto todavía no existen.

```bash
make dev        # servidor base con /healthz y estáticos
make seed-demo  # carga el dataset sintético; requiere el esquema migrado
make demo       # no implementado: requiere la interfaz (T028+)
make corpus     # no implementado: requiere T045
```

## Base de datos

El esquema se crea y evoluciona solo con Alembic. La aplicación no crea tablas al arrancar; al
iniciar reconcilia el estado de las operaciones que quedaron abiertas.

```bash
uv run alembic upgrade head
uv run alembic downgrade base
```

## Pruebas

```bash
make test              # pruebas rápidas
make test-integration  # pruebas con Ollama y recuperación reales
make check             # lint + formato + pruebas
```

Estado actual: la base cubre configuración, motor y esquema, alcance, arranque, transacciones,
seed, fixtures y ciclo de vida de ejecuciones. Las pruebas de integración se incorporarán con la
ingesta y la consulta.

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
- La aplicación arranca con `/healthz` y estáticos; las rutas de producto, la ingesta y el agente
  todavía no existen. `demo` y `corpus` siguen sin implementar.

## Contribución

Lee [`CONTRIBUTING.md`](CONTRIBUTING.md) y [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). Los cambios
arquitectónicos, tecnológicos o de proceso actualizan la constitución en el mismo commit.

## Licencia

[MIT](LICENSE).
