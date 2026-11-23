# Implementation Plan: Generador configurable (Ollama, DeepSeek y Claude Haiku)

**Branch**: `005-generador-configurable` (no creada en este paso) | **Date**: 2026-11-22 | **Spec**:
[spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-generador-configurable/spec.md`

**Note**: Planificación únicamente. No se instala nada, no se modifica código de producto, no se
ejecutan llamadas externas y no se declara aceptación.

## Summary

Añadir una selección explícita del generador entre Ollama local, DeepSeek (`deepseek-flash`) y
Anthropic Claude Haiku (`claude-haiku-5-5`), conservando el grafo, la recuperación Qdrant, la memoria,
`findings_query`, las citas, la reparación y la abstención. La configuración vive en `.env`/entorno,
se valida al arrancar y no tiene fallback. Los proveedores externos quedan detrás de una frontera de
datos por caso, un control de contexto específico, un libro de presupuesto local y un registro de uso
y costo con tarifa fechada.

## Technical Context

**Language/Version**: Python 3.14.6

**Primary Dependencies**: FastAPI, Jinja2, HTMX, SQLAlchemy, Alembic, pydantic-settings, httpx,
LangChain/LangGraph, qdrant-client, pytest. No se añaden SDKs en la primera entrega; `httpx` ya está
instalado.

**Storage**: SQLite (fuente de verdad, presupuesto y autorizaciones), Qdrant (índice documental),
`.env` local excluido de Git.

**Testing**: pytest (unit, contract, integration, acceptance); Ollama real para integración local;
proveedores externos solo con credencial y presupuesto explícitos.

**Target Platform**: aplicación local de un solo proceso y un worker, macOS/Linux.

**Project Type**: aplicación web monolítica modular con CLI de mantenimiento.

**Performance Goals**: conservar los límites actuales (120 s por turno, 90 s por llamada, 8
operaciones, 2 herramientas, 1 reparación). La latencia externa se mide y se reporta; no se promete
un tiempo de respuesta del proveedor.

**Constraints**: sin fallback; sin cambio de proveedor en un turno; sin secretos en logs/SQLite/
trazas; sin contenido privado en proveedores externos sin autorización; sin llamadas pagadas sin
presupuesto; sin cambios en embeddings/Qdrant/Qualys.

**Scale/Scope**: un caso por consulta, una generación global a la vez, tres proveedores, diez
preguntas de comparación.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Verificación | Estado |
|---|---|---|
| I. Propósito y alcance | La funcionalidad no certifica, no remedia y no adquiere proveedores nuevos | PASS |
| III. Arquitectura modular | Un grafo; adaptadores por proveedor; sin microservicios | PASS |
| IV. Persistencia local e inferencia autorizada | Ollama se conserva; selección explícita; sin fallback; modelos versionados; un modelo grande a la vez | PASS |
| V. Recuperación verificable | Qdrant y embeddings no cambian; citas desde SQLite | PASS |
| VII. Seguridad | Alcance impuesto en código; argumentos no conceden permisos; datos no confiables | PASS |
| VIII. Evidencia y revisión | Proveedor, modelo, uso, costo y errores registrados; revisión humana separada | PASS |
| IX. Pruebas y datos | Pruebas con datos públicos/ficticios; externas condicionadas; regresión local obligatoria | PASS |
| XI. Observabilidad y costos | Presupuesto local, reserva antes de la llamada, uso/costo registrados, sin secretos | PASS |
| XIII. Frontera de datos | Autorización por caso, Qualys fuera, LangSmith independiente, sin afirmar retención cero | PASS |
| XIV. Acciones controladas | No aplica: 005 no añade acciones externas | N/A |

**Post-diseño**: el diseño de §Phase 1 conserva los gates. La autorización externa por caso y el
libro de presupuesto son mecanismos nuevos, no excepciones a los principios.

## Project Structure

### Documentation (this feature)

```text
specs/005-generador-configurable/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── provider-adapter.md
│   ├── configuration.md
│   ├── budget.md
│   └── privacy.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/secguard_advisor/
├── config.py                         # selección, límites, credenciales, presupuesto
├── conversation/
│   ├── llm.py                        # modelos Pydantic y errores comunes
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── base.py                   # protocolo Generator y ProviderIdentity
│   │   ├── ollama.py                 # adaptador actual, sin cambio funcional
│   │   ├── deepseek.py               # JSON Output + httpx
│   │   ├── anthropic.py              # Structured Outputs + count_tokens + httpx
│   │   ├── registry.py               # selección explícita al arrancar
│   │   ├── context.py                # PromptCounter por proveedor
│   │   ├── cost.py                   # tarifa fechada y cálculo
│   │   └── redaction.py              # minimización y redacción
│   ├── budget.py                     # admisión de contexto común
│   ├── nodes.py                      # uso y costo por paso
│   └── turn.py                       # registro de proveedor/uso/costo
├── evidence/
│   ├── runs.py                       # creación y cierre de ejecución
│   └── tracing.py                    # metadatos acotados, sin contenido
├── db/
│   └── models.py                     # columnas y tablas nuevas
├── alembic/versions/                 # migración aditiva
├── web/
│   ├── errors.py                     # códigos nuevos
│   └── templates/runs/show.html      # proveedor, uso y costo
└── cases/
    └── external.py                   # autorización externa por caso

tests/
├── unit/
├── contract/
├── integration/
└── acceptance/
```

**Structure Decision**: monolito modular existente. No se crea un paquete de proveedores fuera de
`conversation/providers/`; no se duplica el grafo ni la recuperación.

## Phase 0 — Research (completado)

Decisiones en [research.md](./research.md): identificadores y tarifas verificados, frontera de
adaptador, esquema estructurado, admisión de contexto, uso/costo/presupuesto, secretos, privacidad,
errores, dependencias, razonamiento y comparación.

## Phase 1 — Design

1. [data-model.md](./data-model.md): entidades, columnas, estados y migración.
2. [contracts/provider-adapter.md](./contracts/provider-adapter.md): protocolo y errores.
3. [contracts/configuration.md](./contracts/configuration.md): variables, precedencia y validación.
4. [contracts/budget.md](./contracts/budget.md): reserva, liquidación, reconciliación y límites.
5. [contracts/privacy.md](./contracts/privacy.md): autorización, minimización y Qualys.
6. [quickstart.md](./quickstart.md): arranque local, configuración ficticia y comparación.
7. [tasks.md](./tasks.md): tres entregas funcionales.

## Additional scope — Configuración de IA UI

- Página `/settings/ai` con FastAPI/Jinja2/HTMX; fuera del contexto de caso.
- Tablas `ai_configuration` y `ai_provider_profiles`; perfiles independientes.
- `resolve_turn_settings` toma una instantánea por turno; `_run_generation` construye generador,
  contador, budget y timeout desde esa instantánea.
- La UI no modifica `.env`, no llama proveedores ni cuenta tokens remotos.
- Ollama no usa presupuesto monetario; su reserva de salida es automática dentro del contexto. Los
  límites externos se validan por proveedor/modelo. «Configuración de IA» vive en Administración.
- `_run_generation` cierra generador, contador, embeddings e índice solo cuando son propiedad del
  turno; conserva el release del permiso global.
- Autorización por caso, Qualys, presupuestos, LangSmith, Qdrant y embeddings no cambian.

## Phase 2 — Tasks

Tres entregas, cada una con implementación, pruebas y documentación:

1. **Configuración y contrato común, conservando Ollama.** `ProviderProfile`, validación de arranque,
   credenciales, registro de proveedor/modelo, protocolo común, `ToolDecision` tipado y pruebas.
2. **Adaptadores externos y controles de datos, contexto y costos.** DeepSeek, Anthropic, admisión de
   contexto, presupuesto, uso/costo, autorización externa, redacción, errores y pruebas de contrato.
3. **Comparación, regresión y documentación final.** Conjunto reproducible, comparación condicionada,
   regresión local, documentación y aceptación.

## Testing Strategy

- **Unit**: configuración, precedencia, validación, redacción, cálculo de costo, reserva,
  normalización de errores, esquema tipado.
- **Contract**: cada adaptador contra un servidor HTTP simulado; Anthropic structured outputs y
  count_tokens; DeepSeek JSON Output y contenido vacío; Ollama sin cambio.
- **Integration**: Ollama real obligatorio; externos solo con credencial y presupuesto, omitidos con
  motivo si faltan.
- **Acceptance**: recorrido de consulta con proveedor seleccionado; frontera de datos; presupuesto;
  evidencia de ejecución; sin secretos.
- **Regression**: `make check` y `make test-integration` en el cierre, no después de cada cambio
  menor.

## Migration and Compatibility

- Migración Alembic aditiva: columnas nuevas en `runs`, tablas `provider_usage`,
  `provider_budget_ledger` y `external_processing_authorizations`.
- Ejecuciones existentes conservan sus valores; `generator_provider` se rellena con `ollama` para
  filas previas.
- No se modifican documentos, fragmentos, vectores, Qualys ni datos del usuario.
- `CONSTITUTION.md` sigue siendo el enlace simbólico; cualquier decisión normativa se registra en el
  archivo real.

## Risks and Mitigations

| Riesgo | Mitigación |
|---|---|
| Cambio de modelo/precio | Tarifa fechada y revalidación antes de aceptar |
| Fuga de contenido privado | Autorización por caso + minimización + pruebas de denegación |
| Costo real mayor que la reserva | Reserva conservadora, diferencia registrada, sin promesa de tope exacto |
| JSON inválido o vacío | Reparación acotada, validación local y abstención |
| Contexto mal medido | Medición por proveedor y margen; reducción antes de enviar |
| Secreto en un error | Redacción centralizada y pruebas de escaneo |
| Divergencia entre proveedores | Mismo grafo, mismas pruebas de contrato y comparación reproducible |

## Complexity Tracking

No se introduce complejidad arquitectónica no justificada. La única complejidad nueva es la frontera
de datos y el libro de presupuesto, exigidos por la constitución para inferencia externa.
