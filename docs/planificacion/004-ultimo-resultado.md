# 004 — Último resultado (Corte 5 completado)

**Fecha**: 2026-11-22 12:30–12:33 (America/Bogota, `-05`)
**Rama**: `004-qdrant-vector-index`
**Alcance**: Corte 5, T065–T069 (5 tareas). **Acumulado: T001–T069 = 69 de 82 tareas.**
**Backend**: Qdrant es el índice de la aplicación; Chroma se conserva hasta el Corte 6. SQLite sigue
siendo la fuente de verdad. No se declara aceptación de 004.

## Estado por tarea

| Tarea | Estado | Evidencia |
|---|---|---|
| T065 aislamiento de instancias | Completada | `tests/integration/test_qdrant_instances.py` (3 pruebas) y comprobación con servidor real. |
| T066 lock entre procesos | Completada | `tests/integration/test_qdrant_lock_processes.py` (2 pruebas con procesos reales). |
| T067 integración residual del lock | Completada | Verificación de los tres escritores; sin cambios de código ni primitiva duplicada. |
| T068 verificación de aislamiento y lock | Completada | 5 pruebas de instancias + procesos en verde. |
| T069 sin tablas ni migraciones | Completada | `git diff --stat -- alembic/` vacío; persistencia de casos y rutas de control en verde. |

## Cambios realizados

- Pruebas nuevas: aislamiento de dos instancias con el mismo `case_id`, separación de colecciones,
  alias, corpus público, resultados y evidencia; copia de almacenamiento que falla cerrada sin
  escribir ni cambiar aliases.
- Pruebas con procesos reales: exclusión mutua ingesta/reconstrucción, liberación normal, SIGKILL,
  registro de propietario obsoleto ignorado, alias conservado y recuperación posterior.
- Prueba de rutas: marcadores, locks y reportes viven en `qdrant-control/`, fuera de `storage/qdrant`.
- Sin cambios de código: la integración del lock ya existía en los tres escritores.

## Comandos y resultados

```text
T065/T068: uv run pytest tests/integration/test_qdrant_instances.py \
  tests/integration/test_qdrant_lock_processes.py → 5 passed
T069: git diff --stat -- alembic/ → vacío
      uv run pytest tests/integration/test_case_persistence.py tests/unit/test_qdrant_paths.py → 2 passed
make check → 543 passed, 35 deselected
pre-commit → Passed
```

## Instancias, procesos y servidor real

- **Embebido**: aislamiento por namespace, evidencia con `instance_id` correcto y copia de storage con
  `instance_namespace_mismatch`.
- **Entre procesos**: dos procesos reales con sincronización por archivos de señal (sin pausas
  arbitrarias); el contendiente recibe `ingestion_in_progress`; tras SIGKILL el lock se libera, el
  registro residual no se interpreta como activo y el alias anterior se conserva.
- **Servidor real** (Qdrant 1.20.0, instancias `cut5-a`/`cut5-b`, storage temporal):

```text
case_a: ['1111…'] case_b: ['2222…']
public_a: ['3333…'] public_b: ['4444…']
evidence_instance: cut5-a generation: True
copy_mismatch: instance_namespace_mismatch
```

Servicio detenido con `make qdrant-down` (sin `-v`); volumen conservado.

## Interfaz

El Corte 5 no cambia la interfaz ni la evidencia visible: solo pruebas de aislamiento y concurrencia.
No se repitió la revisión visual con Playwright; no había cambio que validar.

## Limitaciones

- Sin calibración de umbral (Corte 6).
- Chroma y sus datos permanecen.
- El volumen local de Qdrant conserva colecciones de smokes propios.
- Sin aceptación integral de 004.

## Commits

`900d139` pruebas de aislamiento y lock · `fd7a5be` corrección del lock de ingesta (previo).

## Siguiente paso

Corte 6 (T070–T082): retiro de Chroma, calibración, evaluación, constitución y cierre. No se inició
T070.
