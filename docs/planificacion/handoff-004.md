# Handoff 004 — Migración del índice documental a Qdrant

**Fecha de este registro**: 2026-11-22
**Alcance**: continuidad entre sesiones para la funcionalidad `004-qdrant-vector-index`.
**Contenido**: solo hechos comprobados con los comandos indicados. Este documento no implementa, no
aprueba y no declara verificado ningún comportamiento de 004.

---

## 1. Funcionalidad activa

`specs/004-qdrant-vector-index/` es la funcionalidad en curso. Sustituye Chroma por Qdrant como único
índice documental, con índice nuevo construido desde los fragmentos persistidos en SQLite. La
funcionalidad `003` sigue suspendida y `005`–`007` no se inician.

Fuentes de alcance vigente: `AGENTS.md`, `README.md`,
`docs/planificacion/hoja-ruta-mejoras-profesor.md` (§5.1), `.specify/memory/constitution.md` (1.3.0).

---

## 2. Estado de Git y del árbol de trabajo

Verificado con `git branch -vv`, `git log --oneline -3`, `git status --short` y
`git status --porcelain --untracked-files=all`:

- Rama actual: `002-qualys-findings-import`.
- `HEAD`, `main` y `origin/main` apuntan a `edebd6a docs: refine 004 instance lifecycle and index
  coordination`.
- Los tres últimos commits: `edebd6a`, `34f6d15 docs: ratify constitution 1.3.0 and plan 004
  Qdrant`, `fdd453d docs: add 004 Qdrant vector index specification`.
- Archivos modificados rastreados: **ninguno**.
- Archivos sin seguimiento al hacer esta comprobación: **uno**,
  `specs/004-qdrant-vector-index/tasks.md`.
- No hay otros cambios sin seguimiento ni archivos borrados.

Consecuencia: antes de crear este documento, el único trabajo no persistido en Git era `tasks.md`.
Este mismo handoff (`docs/planificacion/handoff-004.md`) se añade después de esa comprobación y
también queda sin seguimiento hasta que se autorice un commit. Todo lo demás de 004 está commiteado
en `edebd6a`.

---

## 3. Artefactos existentes de 004

Listados con `ls -1 specs/004-qdrant-vector-index`:

| Archivo | Rol |
|---|---|
| `spec.md` | Requisitos FR-001–FR-058, criterios SC-001–SC-024 e historias US1–US7 |
| `plan.md` | Arquitectura, namespace de instancia, ciclo del primer documento, lock y estrategia |
| `research.md` | Decisiones técnicas y versiones fijadas |
| `data-model.md` | Instancia, puntos, payload, locks y estados |
| `contracts/index-adapter.md` | Contrato del adaptador de índice |
| `contracts/rebuild.md` | Contrato de reconstrucción |
| `contracts/retrieval.md` | Contrato de recuperación |
| `contracts/evidence.md` | Contrato de evidencia de ejecución |
| `quickstart.md` | Comandos y escenarios de aceptación |
| `checklists/requirements.md` | Calidad de la especificación y decisiones diferidas |
| `tasks.md` | Tareas de implementación (sin seguimiento en Git) |

Constitución vigente: versión **1.3.0**, ratificada 2026-11-08, última enmienda 2026-11-11
(`CONSTITUTION.md`, línea de versión).

---

## 4. Estado de `tasks.md`

Verificado con `grep -c "^- \[ \] T[0-9]"` y `grep -c "^- \[x\]"`:

- **68 tareas** generadas, T001–T068 (registro histórico; el total vigente es 78, ver §10).
- **0 tareas completadas**; ninguna casilla marcada.
- Cortes: Cut 1 T001–T009 (9), Cut 2 T010–T028 (19), Cut 3 T029–T039 (11), Cut 4 T040–T050 (11),
  Cut 5 T051–T056 (6), Cut 6 T057–T068 (12).
- Validación mecánica del documento: IDs únicos y contiguos, sin ciclos, sin dependencias hacia
  adelante, sin referencias inexistentes, todas las tareas con `Dep`, `Check`, `Evidence` y archivo o
  comando concreto.
- MVP funcional propuesto: Cut 1 + Cut 2. Primer corte recomendado: Cut 1 (T001–T009).

Ninguna tarea de `tasks.md` se ejecutó.

---

## 5. Decisiones autorizadas y restricciones vigentes

Registradas en `plan.md`, `research.md`, `quickstart.md` y la constitución 1.3.0:

**Decisiones**
- Qdrant en servidor local persistente con Docker Compose, accesible solo por loopback.
- Imagen `qdrant/qdrant:v1.20.0`; cliente `qdrant-client==1.20.0`; métrica COSINE; 768 dimensiones.
- Índice reconstruido desde los fragmentos de SQLite regenerando embeddings con EmbeddingGemma
  local. No se migran ni exportan vectores de Chroma.
- Reconstrucción con generación y alias; el alias solo se activa tras validar IDs, conteos y payloads.
- `SECGUARD_INSTANCE_ID` explícito y estable, con marcador `storage/qdrant/instances/<id>.json`
  (SHA-256 del storage), colecciones/alias por instancia y lock de archivo en
  `storage/qdrant/locks/<instance_id>.lock`.
- El primer documento de un caso crea la generación/alias del caso solo tras validar; un fallo deja la
  versión no disponible.
- “Alcance vacío” se distingue de “índice esperado ausente” calculando lo esperado desde SQLite.
- Evidencia en `RunStep.detail_json` y reporte JSON de reconstrucción, sin tablas SQLite nuevas.
- Chroma se retira del código y de las dependencias, pero sus archivos y datos **no se borran**.
- La ratificación del responsable está registrada en la constitución. No constan acuerdos de Cristian
  Quebrada ni de Ruben Dario Sabogal; no se inventan ni se solicitan de nuevo.

**Restricciones**
- Sin escritura dual, sin selección de backend, sin fallback a Chroma y sin comparación obligatoria.
- Sin cambios al generador; la selección Ollama/DeepSeek/Claude es de 005 y no se implementa aquí.
- 003 permanece suspendida; 006 (acción externa) y las prioridades P1–P4 no se abordan.
- Qualys permanece en SQLite y fuera del índice documental; su CSV privado no se usa para pruebas RAG.
- Pruebas solo con corpus público o fixtures ficticios, en almacenamiento separado.
- No se publica, no se hace push, no se despliega y no se crean commits sin autorización explícita.
- No se descargan corpus ni se cargan modelos grandes sin una tarea que lo autorice.
- No se declaran resultados, métricas ni estados de CI antes de ejecutarlos.

---

## 6. Último paso completado y siguiente paso

**Completado**: generación y revisión de `specs/004-qdrant-vector-index/tasks.md` (68 tareas en ese
momento; el total vigente es 78, ver §10), cortes,
dependencias y mapa de cobertura FR/SC). No se ejecutó `/speckit.analyze` ni `/speckit.implement`.

**Siguiente paso pendiente (requiere autorización del usuario)**: ejecutar `/speckit.analyze` sobre
los artefactos de 004. Después, y solo con autorización explícita, iniciar el Cut 1 (T001–T009) con
`/speckit.implement` o implementación equivalente.

Nada de 004 está implementado. Prueba observable: `pyproject.toml` sigue declarando
`langchain-chroma>=1.1.0` y no contiene `qdrant-client`; `compose.qdrant.yml` no existe.

---

## 7. Error de Engram

El intento de guardar el resumen de la revisión de `tasks.md` en Engram falló:

```text
gentle-engram could not resolve an authoritative OpenCode runtime session for mem_save
[foreign-project]. Reopen the session in the current project and retry; if it persists,
check OpenCode runtime session metadata.
```

No se intentó eludir el error: no se cambió de proyecto, no se inventó un `session_id`, no se guardó
en otro alcance y no se repitió la operación con parámetros alterados. Este documento sustituye al
resumen que no pudo persistirse en Engram.

---

## 8. Cómo continuar en una sesión nueva

1. Leer `AGENTS.md`, `.specify/memory/constitution.md` y `specs/004-qdrant-vector-index/plan.md`.
2. Leer `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md` y
   `checklists/requirements.md` de 004.
3. Leer `specs/004-qdrant-vector-index/tasks.md` completo, incluidas las secciones de dependencias y
   cobertura.
4. Confirmar el estado con `git status --short` y `git log --oneline -3`; el único archivo sin
   seguimiento esperado es `tasks.md`.
5. Pedir autorización antes de `/speckit.analyze` y antes de cualquier implementación.

---

## 9. Pendientes no verificados

Siguen sin comprobar y no deben presentarse como aprobados:

- Disponibilidad y rendimiento de `qdrant/qdrant:v1.20.0` en arm64 (tarea T009).
- Levantamiento de servicios Qdrant, persistencia tras reinicio y comportamiento del lock entre
  procesos reales (T035–T039, T053–T054).
- Calibración del umbral de recuperación con Qdrant y separación entre calibración y evaluación final
  (T061–T064); no se copia 0.35 de Chroma.
- Cualquier prueba, migración, reconstrucción de índice o medición de 004.

---

## 10. Actualización tras el análisis de consistencia (2026-11-22)

Se aplicó la reconciliación documental del análisis de consistencia de 004. Las secciones 1–9 se
conservan como registro de la sesión anterior; donde citan números de tarea, la referencia vigente es
`specs/004-qdrant-vector-index/tasks.md`:

- Total actualizado: **78 tareas (T001–T078)** y **6 cortes**. Ninguna tarea ejecutada ni completada.
- Los pendientes de §9 corresponden ahora a: arm64 y salud T009; persistencia, disponibilidad y lock
  T045–T049 y T062–T064; calibración y evaluación T070–T074.
- Correcciones aplicadas: taxonomía de errores con códigos y estados propios; propagación del fallo de
  índice en el turno sin abstención; fingerprint del marcador por ruta canónica e identidad de
  instancia; cinco estados observables de reconstrucción; frontera de atomicidad Qdrant/SQLite;
  puntos huérfanos reportados; comando y reporte como interfaz operativa; retiro de Chroma como
  unidad única; ingesta del corpus público dentro del Corte 2; actualización de
  `.specify/memory/constitution.md` asignada al commit del cambio de backend.
- Siguiente paso: repetir `/speckit.analyze` sobre los artefactos corregidos antes de implementar.
  No se ejecutó `/speckit.implement`, no se creó commit y no se modificó almacenamiento del usuario.

---

## 11. Estado tras la segunda reconciliación y el análisis (2026-11-22 08:56)

Se aplicaron cuatro correcciones adicionales y se ejecutó `/speckit.analyze` sobre los artefactos
corregidos, en solo lectura.

### Cambios de esta pasada

1. **Orden de pruebas y adaptación**: T033 es la prueba de contrato RED del mapeo de errores
   (Dep T017, T031; Verifies T034) y T034 la adaptación de fábrica y rutas (Dep T032, T033). La misma
   clase de defecto se corrigió en T054 y T062, convertidas en verificación de integración.
2. **Calibración y evaluación**: T074 depende de T072 y T073; usa el umbral aplicado y congelado en
   `config.py` y un conjunto distinto del de calibración.
3. **Lock en los escritores iniciales**: T019 (corpus), T022 (reconstrucción) y T032 (documentos)
   adquieren y liberan el lock con su operación; T063 queda como verificación residual. T062 conserva
   la prueba entre procesos con terminación abrupta.
4. **Identificación del lock**: nuevo FR-059 con registro `{operation, attempt_id, pid, started_at}`
   asociado al bloqueo real; los metadatos residuales con el lock libre se ignoran y el estado
   distingue ingesta activa, reconstrucción activa y último resultado terminal.

### Estado vigente

- **59 requisitos** (FR-001–FR-059), **24 criterios** (SC-001–SC-024), **7 historias** y
  **78 tareas** (T001–T078) en **6 cortes** de 9 / 29 / 11 / 11 / 5 / 13 tareas.
- 0 tareas ejecutadas o completadas. Sin cambios en código, pruebas, dependencias ni almacenamiento.
- Cobertura 59/59 FR y 24/24 SC; sin dependencias inválidas, ciclos ni dependencias a cortes
  posteriores.

### Resultados guardados

- Informe completo del análisis:
  `specs/004-qdrant-vector-index/analyses/2026-11-22-0850-analyze.md`
- Resumen y comprobaciones:
  `docs/planificacion/004-ultimo-resultado.md`

### Hallazgos abiertos

- **A1 (MEDIUM)**: la constitución no debe declarar Qdrant «implementado» antes de la aceptación; T068
  debe registrar el estado intermedio y T078 completar «implementado y aceptado».
- **A2 (LOW)**: el texto del Corte 5 declara una dependencia del Corte 3 que ninguna tarea codifica.
- **A3 (MEDIUM)**: falta definir el punto de lectura del estado del lock (ingesta activa vs
  reconstrucción activa) sin intentar reconstruir; se propone `--status` o ampliar `make qdrant-health`.

### Cómo continuar

1. Leer `docs/planificacion/004-ultimo-resultado.md` y el informe de análisis.
2. Resolver A1–A3 en una pasada documental breve.
3. Repetir `/speckit.analyze` sobre los artefactos corregidos.
4. Con autorización explícita, iniciar el Corte 1 (T001–T009).

No constan acuerdos de Cristian Quebrada ni Ruben Dario Sabogal; no se inventan. La ratificación del
responsable está registrada. No se creó commit ni se publicó nada.

---

## 12. Estado tras A1–A3 y tercera pasada de análisis (2026-11-22 09:04)

Los IDs de tarea citados en §10 y §11 corresponden a la numeración de 78 tareas. Con A3 se añadieron
T024/T025 y la numeración vigente pasa a **80 tareas (T001–T080)**. El mapa actual es
`specs/004-qdrant-vector-index/tasks.md`.

### Correcciones de esta pasada

- **A1**: la constitución se actualiza en dos etapas. T070 registra «backend sustituido; aceptación
  pendiente» al retirar Chroma; T080 registra «implementado y aceptado localmente» solo después de
  T079 y con evidencia observada. Sin copia de la constitución.
- **A2**: el Corte 5 depende del Corte 2 (escritores integrados) y toma la primitiva del lock del
  Corte 1; se eliminó la referencia ficticia a evidencia del Corte 3.
- **A3**: `uv run python scripts/rebuild_qdrant.py --status` es una consulta de solo lectura con seis
  valores (`not_started`, `ingestion_in_progress`, `rebuild_in_progress`, `completed`, `partial`,
  `failed`), salida 0 sin estado registrado y sin efectos de escritura. T024 prueba, T025 implementa y
  T031 verifica.

### Estado vigente

- 59 requisitos (FR-001–FR-059), 24 criterios (SC-001–SC-024), 7 historias.
- 80 tareas (T001–T080), 6 cortes: 9 / 31 / 11 / 11 / 5 / 13.
- 0 tareas ejecutadas. Sin cambios en código, pruebas, dependencias ni almacenamiento.
- Cobertura 59/59 FR y 24/24 SC; sin dependencias inválidas, ciclos ni dependencias a cortes
  posteriores; 80/80 tareas con `Check` y `Evidence`.

### Primer corte y dependencias

**Corte 1 — T001–T009 (9 tareas), autocontenido.**

| Tarea | Depende de |
|---|---|
| T001 fijar `qdrant-client==1.20.0` y `uv.lock` | none |
| T002 `compose.qdrant.yml` en loopback con volumen | none |
| T003 configuración de instancia y Qdrant en `config.py` | none |
| T004 `.env.example` | T003 |
| T005 targets `qdrant-up/down/health` con `##` | T002, T003 |
| T006 pruebas unitarias de instancia, marcador, lock e `inspect` | T003 |
| T007 implementar `retrieval/instance.py` | T006 |
| T008 contrato de despliegue | T002, T003, T004, T005 |
| T009 verificar arm64 y salud local | T002, T005, T006, T007 |

Cierre: `uv lock --check`, `docker compose config`, pruebas de instancia y contrato en verde, fallos de
ID/namespace explícitos, `/readyz` en arm64, sin modificar SQLite ni borrar Chroma.

### Resultados guardados

- `docs/planificacion/004-ultimo-resultado.md`
- `specs/004-qdrant-vector-index/analyses/2026-11-22-0900-analyze.md`
- Informe anterior conservado: `specs/004-qdrant-vector-index/analyses/2026-11-22-0850-analyze.md`

### Pendientes

Dos hallazgos LOW del último análisis:

- **B1**: falta fijar salida y forma del resultado de `--status` cuando `latest.json` es ilegible, y su
  caso de prueba.
- **B2**: unificar la resolución de estado en un solo responsable consumido por el reporte y por
  `--status`.

### Cómo continuar

1. Leer este handoff y `docs/planificacion/004-ultimo-resultado.md`.
2. Cerrar B1 y B2 en una pasada documental breve.
3. Repetir `/speckit.analyze`.
4. Con autorización explícita, iniciar el Corte 1 (T001–T009) según la tabla anterior.

No constan acuerdos de Cristian Quebrada ni Ruben Dario Sabogal; no se inventan. La ratificación del
responsable está registrada. No se creó commit ni se publicó nada.

---

## 13. Estado vigente tras cerrar B1 y B2 (2026-11-22 09:16)

**Las secciones §10, §11 y §12 son históricas.** Sus números de tarea corresponden a estados
anteriores (78, 80 y 82 tareas respectivamente). La referencia vigente es esta sección y
`specs/004-qdrant-vector-index/tasks.md`.

### Correcciones de esta pasada

- **B1**: `--status` ante reporte terminal ilegible devuelve salida 2, mensaje en `stderr` y JSON con
  `state: null`, `last_terminal: null` y `error: {code, message}`; no lo presenta como `not_started`,
  no inventa estado y no borra, sobrescribe ni repara el reporte. T026 prueba, T027 implementa.
- **B2**: `src/secguard_advisor/retrieval/status.py` es el resolvedor único
  (`resolve_operation_state`, `terminal_status`). T023 prueba, T024 implementa, T025 (reporte) y T027
  (`--status`) consumen el mismo módulo, y T033 verifica. La consulta sigue sin efectos de escritura.

### Estado vigente

- 59 requisitos (FR-001–FR-059), 24 criterios (SC-001–SC-024), 7 historias.
- **82 tareas (T001–T082)**, 6 cortes: 9 / 33 / 11 / 11 / 5 / 13.
- 0 tareas ejecutadas. Sin cambios en código, pruebas, dependencias ni almacenamiento.
- Cobertura 59/59 FR y 24/24 SC; sin ciclos, referencias inválidas ni dependencias a cortes
  posteriores; 82/82 tareas con `Check` y `Evidence`.

### Primer corte y dependencias (vigente)

**Corte 1 — T001–T009 (9 tareas), autocontenido.**

| Tarea | Depende de |
|---|---|
| T001 fijar `qdrant-client==1.20.0` y `uv.lock` | none |
| T002 `compose.qdrant.yml` en loopback con volumen | none |
| T003 configuración de instancia y Qdrant en `config.py` | none |
| T004 `.env.example` | T003 |
| T005 targets `qdrant-up/down/health` con `##` | T002, T003 |
| T006 pruebas unitarias de instancia, marcador, lock e `inspect` | T003 |
| T007 implementar `retrieval/instance.py` | T006 |
| T008 contrato de despliegue | T002, T003, T004, T005 |
| T009 verificar arm64 y salud local | T002, T005, T006, T007 |

Cierre: `uv lock --check`, `docker compose config`, pruebas de instancia y contrato en verde, fallos de
ID/namespace explícitos, `/readyz` en arm64, sin modificar SQLite ni borrar Chroma.

### Resultados guardados

- `docs/planificacion/004-ultimo-resultado.md` (estado vigente)
- `specs/004-qdrant-vector-index/analyses/2026-11-22-0912-analyze.md` (informe vigente)
- Informes históricos conservados: `2026-11-22-0850-analyze.md` y `2026-11-22-0900-analyze.md`

### Pendiente

- **B3 (LOW)**: falta definir salida y JSON de `--status` ante configuración de instancia inválida o
  ausente y ante lock ilegible por permisos; usar el mismo formato de error y añadir los casos a
  T026/T027.

### Cómo continuar

1. Leer `docs/planificacion/004-ultimo-resultado.md` y el informe vigente.
2. Cerrar B3 en una pasada documental breve.
3. Repetir `/speckit.analyze`.
4. Con autorización explícita, iniciar el Corte 1 (T001–T009).

No constan acuerdos de Cristian Quebrada ni Ruben Dario Sabogal; no se inventan. La ratificación del
responsable está registrada. No se creó commit ni se publicó nada.

---

## 14. Estado vigente tras cerrar B3 (2026-11-22 09:22)

**Esta es la sección vigente.** Las secciones §10–§13 son históricas y conservan numeraciones
anteriores; la referencia actual es esta sección y `specs/004-qdrant-vector-index/tasks.md`.

### Corrección de esta pasada

B3 cerrado: `--status` completa tres errores con salida 2, mensaje en `stderr` y JSON
`{state: null, last_terminal: null, error: {code, message}}`:

| Situación | `error.code` |
|---|---|
| Configuración de instancia ausente o inválida | `instance_configuration_invalid` |
| Archivo de lock ilegible, o lock tomado con registro de propietario ausente o corrupto | `lock_unreadable` |
| Reporte terminal ilegible | `status_report_unreadable` |

En los tres casos no se devuelve `not_started`, no se afirma que no existe una operación activa y no se
crea ni repara ningún archivo. El resolvedor único sigue en `retrieval/status.py` (T023 pruebas, T024
implementación, T025/T027 consumidores, T033 verificación; T026 cubre los escenarios por CLI).

### Estado vigente

- 59 requisitos (FR-001–FR-059), 24 criterios (SC-001–SC-024), 7 historias.
- **82 tareas (T001–T082)**, 6 cortes: 9 / 33 / 11 / 11 / 5 / 13.
- 0 tareas ejecutadas. Sin cambios en código, pruebas, dependencias ni almacenamiento.
- Cobertura 59/59 FR y 24/24 SC; sin ciclos, referencias inválidas ni dependencias a cortes
  posteriores; 82/82 tareas con `Check` y `Evidence`.
- Último análisis: 0 defectos o contradicciones abiertas; 9 observaciones documentales sin corrección
  requerida.

### Primer corte y dependencias (vigente)

**Corte 1 — T001–T009 (9 tareas), autocontenido.**

| Tarea | Depende de |
|---|---|
| T001 fijar `qdrant-client==1.20.0` y `uv.lock` | none |
| T002 `compose.qdrant.yml` en loopback con volumen | none |
| T003 configuración de instancia y Qdrant en `config.py` | none |
| T004 `.env.example` | T003 |
| T005 targets `qdrant-up/down/health` con `##` | T002, T003 |
| T006 pruebas unitarias de instancia, marcador, lock e `inspect` | T003 |
| T007 implementar `retrieval/instance.py` | T006 |
| T008 contrato de despliegue | T002, T003, T004, T005 |
| T009 verificar arm64 y salud local | T002, T005, T006, T007 |

Cierre: `uv lock --check`, `docker compose config`, pruebas de instancia y contrato en verde, fallos de
ID/namespace explícitos, `/readyz` en arm64, sin modificar SQLite ni borrar Chroma.

### Resultados guardados

- `docs/planificacion/004-ultimo-resultado.md` (estado vigente)
- `specs/004-qdrant-vector-index/analyses/2026-11-22-0918-analyze.md` (informe vigente)
- Históricos conservados: `2026-11-22-0850-analyze.md`, `2026-11-22-0900-analyze.md` y
  `2026-11-22-0912-analyze.md`

### Cómo continuar

1. Leer este apartado y `docs/planificacion/004-ultimo-resultado.md`.
2. Iniciar el Corte 1 (T001–T009) con autorización explícita.
3. No se ejecutó `/speckit.implement`, no se creó commit y no se publicó nada.

No constan acuerdos de Cristian Quebrada ni Ruben Dario Sabogal; no se inventan. La ratificación del
responsable está registrada.

---

## 15. Corte 1 ejecutado — estado vigente (2026-11-22 10:05)

**Esta sección es la vigente.** Las secciones §10–§14 son históricas y conservan numeraciones
anteriores; el mapa actual es `specs/004-qdrant-vector-index/tasks.md`.

### Rama y commits

- Rama: `004-qdrant-vector-index` (creada desde `002-qualys-findings-import` conservando los cambios
  documentales).
- `73f304d` docs: reconcile 004 planning and record analysis reports
- `3cd264a` feat(deps): pin qdrant-client 1.20.0
- `62cd7c0` feat(config): add instance and qdrant settings
- `3febecf` feat(retrieval): add instance marker namespace and lock
- `8356acc` feat(qdrant): add local compose and maintenance targets
- Sin push ni publicación.

### Estado del Corte 1 (T001–T009)

- **Completadas (7)**: T001, T003, T004, T005, T006, T007, T008.
- **T002**: `compose.qdrant.yml` creado y YAML válido, pero falta `docker compose config`; Docker no
  está instalado. Permanece abierta.
- **T009**: bloqueada. Faltan `docker manifest inspect qdrant/qdrant:v1.20.0`, `make qdrant-up`,
  `/readyz` y la detención controlada. Evidencia parcial: la etiqueta `v1.20.0` existe y su índice
  incluye `linux/arm64`.

### Qué quedó implementado

- `qdrant-client==1.20.0` en `pyproject.toml` y `uv.lock`; Chroma conservado.
- `compose.qdrant.yml` con imagen fijada, loopback 6333/6334, volumen `./storage/qdrant` y reinicio.
- `config.py` con `SECGUARD_INSTANCE_ID`, `SECGUARD_QDRANT_URL` y timeout; `.env.example` actualizado.
- `Makefile` con `qdrant-up`, `qdrant-down`, `qdrant-health`.
- `retrieval/instance.py`: slug, namespace, marcador con fingerprint por ruta canónica, reglas de
  registro, lock con propietario y sondeo de solo lectura.
- Pruebas: 35 unitarias (instancia y configuración) y 5 de contrato de despliegue.
- `make check`: 452 passed; pre-commit: todo en verde.

### Bloqueo exacto para cerrar el corte

En un equipo con Docker:

```bash
docker compose -f compose.qdrant.yml config
docker manifest inspect qdrant/qdrant:v1.20.0
make qdrant-up
curl -fsS http://127.0.0.1:6333/readyz
make qdrant-down   # conserva el volumen; nunca down -v
```

Si `/readyz` responde 200 y el manifiesto incluye arm64, marcar T002 y T009 con esa evidencia.

### Datos y servicios

No se levantaron servicios, no se ejecutaron migraciones ni reconstrucciones y no se modificó
`storage/`, SQLite, Chroma ni datos del usuario.

### Siguiente paso

1. Cerrar T002 y T009 con Docker.
2. Iniciar el Corte 2 (T010–T042) en una tarea posterior, sin reutilizar el estado de este corte como
   aceptación de Qdrant.

### Evidencia

- `docs/evidencia/004-corte-1/README.md`
- `docs/planificacion/004-ultimo-resultado.md`

No constan acuerdos de Cristian Quebrada ni Ruben Dario Sabogal; no se inventan. La ratificación del
responsable está registrada. No se creó commit remoto ni se publicó nada.

---

## 16. Reintento de verificación del Corte 1 (2026-11-22 09:32)

**Vigente para el estado del Corte 1.** Se repitió la comprobación de Docker sin cambios en el
sistema.

- `docker` y `docker compose` no existen; el `PATH` ya incluye `/usr/local/bin` y `/opt/homebrew/bin`.
- No hay Docker Desktop, OrbStack, Rancher Desktop, Podman ni Colima instalados, ni procesos o
  entradas de `launchctl` relacionadas.
- Fallan `docker compose config`, `docker manifest inspect`, `make qdrant-up` y `make qdrant-health`
  con «command not found» o conexión rechazada en 6333.
- Evidencia estática repetida: imagen `qdrant/qdrant:v1.20.0`, puertos solo loopback, volumen
  `./storage/qdrant`; registro con `linux/amd64` y `linux/arm64`; 40 pruebas en verde.

Estado: **T002 y T009 siguen abiertas**. T001, T003–T008 completadas. No se instaló Docker, no se
arrancó ningún servicio y no se modificó el volumen, SQLite, Chroma ni los datos.

Siguiente paso: repetir las cuatro comprobaciones en un equipo con Docker y, solo entonces, marcar
T002/T009 y comenzar el Corte 2 (T010–T042). No se inició T010.

---

## 17. T002 completado y motor Docker ausente (2026-11-22 09:47)

**Vigente para el estado del Corte 1.** El CLI de Docker ya está instalado por Homebrew:
`docker 29.10.0` y `docker compose 5.8.0`. El motor no está disponible: no existe
`/var/run/docker.sock`, `docker info` falla y no hay Docker Desktop, Colima, Lima, OrbStack ni
Rancher Desktop.

- **T002 completado**: `docker compose -f compose.qdrant.yml config` valida la imagen
  `qdrant/qdrant:v1.20.0`, `host_ip: 127.0.0.1` en 6333/6334, volumen `./storage/qdrant` y
  `restart: unless-stopped`.
- **T009 sigue bloqueado**: `docker manifest inspect` confirma `linux/amd64` y `linux/arm64`, pero
  `make qdrant-up` falla por falta de motor y `make qdrant-health` no conecta a 6333.
- Las comprobaciones de ID y namespace siguen en verde (25 pruebas de instancia).
- No se instaló ni arrancó un motor, no se inició ningún servicio y no se tocó el volumen, SQLite,
  Chroma ni los datos.

Estado del corte: **8 completadas (T001–T008), 1 bloqueada (T009)**.

Siguiente paso: con un motor Docker activo, ejecutar `make qdrant-up`, `make qdrant-health`,
comprobar `/readyz` y `make qdrant-down` conservando el volumen; solo entonces marcar T009 y comenzar
el Corte 2 (T010–T042). No se inició T010.

---

## 18. Corte 1 cerrado — T009 verificado en ejecución (2026-11-22 10:05)

**Vigente.** Las secciones §10–§17 son históricas.

### Estado

- **T001–T009: 9 de 9 completadas.**
- Rama `004-qdrant-vector-index`; sin push.
- Backend documental: **Chroma** (sin cambios). Qdrant queda como infraestructura local preparada.

### Verificación final de T009

- Motor: Docker Desktop 29.9.3, `arch=aarch64`, contexto `desktop-linux`.
- Sin contenedores ni proyectos Compose preexistentes; puertos 6333/6334 libres.
- `make qdrant-up`: imagen `qdrant/qdrant:v1.20.0` descargada y contenedor `secguard-qdrant` iniciado.
- `make qdrant-health`: `/readyz` = «all shards are ready»; versión real del servidor **1.20.0**.
- Puertos publicados: `127.0.0.1:6333` y `127.0.0.1:6334` únicamente.
- `make qdrant-down`: contenedor y red eliminados sin `-v`; volumen `storage/qdrant` conservado
  (`aliases`, `collections`, `raft_state.json`).
- ID inválido y namespace incompatible siguen cubiertos por las 25 pruebas de instancia.

### Evidencia

- `docs/evidencia/004-corte-1/README.md` (incluye el historial de bloqueos por CLI y motor ausentes).
- `docs/planificacion/004-ultimo-resultado.md`.

### Siguiente paso

Iniciar el Corte 2 (T010–T042) en una tarea posterior y con autorización explícita. No se inició T010.

No se modificó SQLite, Chroma ni los datos existentes. No se creó commit remoto ni se publicó nada.

---

## 19. Corte 2 en curso — avance parcial (2026-11-22 10:55)

**Vigente.** Las secciones §10–§18 son históricas.

### Estado

- Rama `004-qdrant-vector-index`.
- **12 tareas del Corte 2 cerradas**: T010–T017, T023, T024, T026, T027.
- **21 pendientes**: T018–T022, T025, T028–T042.
- `make check`: 485 passed. `pre-commit`: todo en verde.
- No se declara aceptación de 004 ni se retiró Chroma.

### Implementado

- Adaptador Qdrant (`QdrantIndex`), colecciones/alias con namespace, UUIDv5, payload sin texto.
- Seis códigos de error 503/409 en `web/errors.py`.
- Fábrica de aplicación con Qdrant y mapeo de fallos de índice a HTTP.
- Resolvedor único de estado y `uv run python scripts/rebuild_qdrant.py --status`.
- Turno que se detiene con el código clasificado ante fallo de índice (cambio de coherencia; T041
  sigue pendiente de sus pruebas).

### Riesgo del estado intermedio

La fábrica ya usa Qdrant, pero `scripts/ingest_corpus.py` y `prepare_demo.py` siguen escribiendo en
Chroma hasta T018–T020. No usar `make corpus-ingest` como fuente del índice Qdrant hasta completar
esas tareas. No hay reconstrucción hasta T021/T022.

### Commits de esta pasada

`a532a91` códigos de error · `cc92007` adaptador y colecciones · `86de5c8` fábrica y mapeo ·
`a41f4fe` parada del turno · `7f2dec7` resolvedor y `--status`.

### Siguiente paso

Continuar en orden: T018–T020 (corpus/demo con lock), T021/T022/T025 (reconstrucción), T028–T033
(fallos, parciales, huérfanos, target, verificación), T034–T039 (recuperación, servicio, rutas) y
T040–T042 (turno). No se inició T043.

Evidencia: `docs/evidencia/004-corte-2/README.md`.

---

## 20. Corte 2 completado (2026-11-22 11:35)

**Vigente.** Las secciones §10–§19 son históricas.

### Estado

- Rama `004-qdrant-vector-index`. **T001–T042 completadas**; 0 abiertas en esos rangos.
- `make check`: 502 passed. `pre-commit`: verde.
- Qdrant es el índice de la aplicación; Chroma se conserva (código, datos y dependencias) hasta el
  Corte 6. SQLite sigue siendo la fuente de verdad.
- No se declara aceptación de 004.

### Implementado

- Adaptador Qdrant, colecciones/alias por instancia y alcance, UUIDv5, payload sin texto.
- Ingesta del corpus y demo con Qdrant y lock por documento; targets sin Chroma.
- Reconstrucción desde SQLite con generación nueva, validación, alias, reporte y estados.
- `--status` de solo lectura con configuración/lock/reporte ilegible (salida 2).
- Recuperación público/caso con score coseno y aislamiento.
- Lock de escritura en el servicio y mapeo 409/503 en rutas.
- Turno detenido con código clasificado, sin generador ni abstención.

### Evidencia

- `docs/evidencia/004-corte-2/README.md` (incluye el smoke real con servidor y EmbeddingGemma).
- `docs/planificacion/004-ultimo-resultado.md`.

### Limitaciones

- Caso sin documentos privados: `case_index_unavailable` hasta T053 (alcance esperado, Corte 4).
- Sin calibración de umbral.
- El volumen local de Qdrant conserva colecciones del smoke `cut2-smoke`.

### Siguiente paso

Corte 3 (T043–T053): citas/evidencia y reinicio/disponibilidad. No se inició T043 ni ninguna tarea
posterior.

---

## 21. Corte 2 corregido (2026-11-22 11:40)

**Vigente.** §10–§20 son históricas.

- Corte 2 = T010–T042 (**33 tareas**); acumulado T001–T042 = **42**.
- Corrección: la publicación del alias depende solo de la candidata; los faltantes/sobrantes de la
  generación anterior se reportan como `previous_missing_chunks`/`previous_extra_chunks` y no
  bloquean. La generación anterior se conserva.
- Corrección: el reporte terminal se construye y publica dentro del lock; se libera incluso si la
  escritura falla.
- Regresiones: huérfano anterior + candidata válida, versión vigente sustituida, candidata defectuosa
  con alias anterior conservado, reporte bajo lock.
- `make check`: 505 passed; `pre-commit`: verde.
- Smoke real con Qdrant servidor y EmbeddingGemma, instancia `cut2-fix-smoke`: tres reconstrucciones
  `completed` (la tercera con `previous_extra_chunks=1`) y recuperación de ambos orígenes.
- Limitaciones: caso sin documentos privados → `case_index_unavailable` hasta T053; sin calibración;
  Chroma conservado; sin aceptación de 004.

Siguiente paso: Corte 3 (T043–T053). No se inició T043.

---

## 22. Corte 3 completado (2026-11-22 11:52)

**Vigente.** §10–§21 son históricas.

- Corte 3: T043–T053 completadas. **Acumulado T001–T053 = 53/82.**
- `make check`: 514 passed; `pre-commit`: verde.
- Versiones vigentes y citas históricas verificadas; `citations.py` no se reimplementó.
- Evidencia del paso `retrieve` con identidad del índice y `error_code`; página de ejecución validada
  con Playwright MCP (`docs/evidencia/004-corte-3/run-detail.png`).
- Qualys sigue fuera del RAG: la importación no crea documentos, fragmentos ni puntos Qdrant.
- Reinicio persistente y disponibilidad: reinicio con cliente reabierto y con servidor real;
  `qdrant_unavailable` e `instance_namespace_mismatch` sin fallback a Chroma.
- Smoke real con Qdrant 1.20.0 + EmbeddingGemma, instancia `cut3-smoke`, storage temporal: dos
  reconstrucciones `completed`, búsqueda sin cruces, versión superada excluida, cita histórica válida,
  reinicio conservado y errores explícitos. Servicio detenido con `make qdrant-down`.
- Limitaciones: caso sin documentos privados → `case_index_unavailable` hasta T054–T059; sin
  calibración; Chroma conservado; colecciones de smokes propios en el volumen local.

Siguiente paso: Corte 4 (T054–T064). No se inició T054 ni ninguna tarea posterior.

---

## 23. Corrección de trazabilidad del Corte 3 (2026-11-22 11:51)

**Vigente.** §10–§22 son históricas.

- Corte 3 corregido: la evidencia del paso `retrieve` captura la identidad dentro de la consulta
  (`query_with_identity`), no con `describe()` posterior. `search_documents` propaga
  `public_evidence`/`case_evidence` y `nodes` las usa.
- Regresión: generación A consultada → alias B → evidencia sigue en A; cubre público, caso y consulta
  sin coincidencias; un índice con `describe()` en B no altera la evidencia de A.
- Contratos y modelo sincronizados (`contracts/evidence.md`, `data-model.md`).
- Avance: **53/82**. `make check` y `pre-commit` al cierre.
- Siguiente paso: Corte 4 (T054–T064). No se inició T054.

---

## 24. Corte 4 completado (2026-11-22 12:15)

**Vigente.** §10–§23 son históricas.

- Corte 4: T054–T064 completadas. **Acumulado T001–T064 = 64/82.**
- Primer documento: generación validada antes de publicar alias; fallo de commit SQLite deja versión
  `failed` y el reintento converge sin duplicados.
- Alcance esperado desde SQLite: caso vacío consulta público; datos sin alias dan
  `case_index_unavailable`/`public_index_unavailable`; público vacío se omite; alias sin hits es
  `empty`; Qdrant caído es `qdrant_unavailable` sin abstención.
- Recuperación y parciales: alias anterior conservado, alcances válidos publicados y global `partial`.
- `make check`: 535 passed; `pre-commit`: verde. Registro del Corte 3: `make check` 517 passed y
  `pre-commit` verde el 2026-11-22 11:51.
- Flujo real con Playwright MCP (Qdrant 1.20.0 + EmbeddingGemma + qwen): crear caso, subir primer
  documento, disponible, consulta con cita válida y control automático «válida». Captura:
  `docs/evidencia/004-corte-4/chat-citation.png`.
- Limitaciones: sin calibración; Chroma conservado; sin aceptación de 004.

Siguiente paso: Corte 5 (T065–T069). No se inició T065.

---

## 25. Corrección de concurrencia del Corte 4 (2026-11-22 12:26)

**Vigente.** §10–§24 son históricas.

- Corregido: la ingesta mantiene el lock hasta confirmar la disponibilidad en SQLite o registrar el
  fallo; una reconstrucción no puede entrar en la ventana.
- Regresión: segundo documento distinto, `rebuild` rechazado con `ingestion_in_progress` durante
  `_mark_available`, ambos documentos recuperables tras reconstruir; fallo de commit libera el lock y
  el reintento converge sin duplicados.
- `make check`: 537 passed; `pre-commit`: verde.
- Contratos y modelo sincronizados. Avance: **64/82**. Sin tareas posteriores.

Siguiente paso: Corte 5 (T065–T069). No se inició T065.

---

## 26. Corte 5 completado (2026-11-22 12:33)

**Vigente.** §10–§25 son históricas.

- Corte 5: T065–T069 completadas. **Acumulado T001–T069 = 69/82.**
- Aislamiento: dos instancias con el mismo `case_id`, colecciones/alias/público/resultados/evidencia
  separados; copia de storage falla con `instance_namespace_mismatch` sin escribir.
- Procesos: exclusión mutua ingesta/reconstrucción, liberación normal y tras SIGKILL, registro
  residual ignorado, alias conservado.
- Escritores verificados: servicio (lock hasta confirmar disponibilidad), reconstrucción (reporte bajo
  lock) e ingesta de corpus vía servicio. Sin primitiva duplicada.
- Sin tablas ni migraciones; control en `qdrant-control/`, separado de `storage/qdrant`.
- `make check`: 543 passed; `pre-commit`: verde. Servidor real: aislamiento y copia incompatible
  verificados; servicio detenido.
- Sin cambios de interfaz: no se repitió Playwright.

Siguiente paso: Corte 6 (T070–T082). No se inició T070 ni se retiró Chroma.

---

## 27. Corte 6 parcial: Qdrant activo, aceptación pendiente (2026-11-22 13:05)

**Vigente.** §10–§26 son históricas.

- Chroma retirado del código y dependencias; `storage/chroma` y sus archivos se conservan.
- Qdrant es el backend documental. Servidor real y EmbeddingGemma.
- Calibración fijada: umbral **0.4956** (relevantes ≥0.4956; no pertinentes ≤0.0861).
- Evaluación independiente: **3/4** escenarios; caso A 0.4359 < umbral. No se ajustó el umbral ni los
  criterios. Informes en `docs/evidencia/004-corte-6/`.
- Constitución: «backend sustituido; aceptación pendiente». `CONSTITUTION.md` sigue siendo enlace.
- `make check`: 550 passed. `make test-integration` pendiente. T079–T082 pendientes.
- 78/82 tareas. Sin aceptación integral.

Siguiente paso: repetir calibración con un conjunto más representativo (sin usar la evaluación),
reevaluar, ejecutar T079 (ASGI/Playwright), T080, T081 y, solo si cumple, T082.
