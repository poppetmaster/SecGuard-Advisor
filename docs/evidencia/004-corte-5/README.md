> **Registro histórico.** Este documento describe el estado del corte en su fecha. Desde el Corte 6,
> Qdrant es el único backend documental y Chroma quedó retirado del código; los archivos de Chroma
> se conservan.

# Corte 5 — Aislamiento de instancias y concurrencia

**Fecha**: 2026-11-22 12:30–12:33 (America/Bogota, `-05`)
**Rama**: `004-qdrant-vector-index`
**Estado**: T065–T069 completadas. Acumulado T001–T069 = 69/82. No se declara aceptación de 004.

## Procedimiento reproducible

```bash
uv run pytest tests/integration/test_qdrant_instances.py \
  tests/integration/test_qdrant_lock_processes.py
uv run pytest tests/integration/test_case_persistence.py tests/unit/test_qdrant_paths.py
git diff --stat -- alembic/
make check
uv run pre-commit run --all-files
```

Resultados:

```text
instancias + procesos: 5 passed
persistencia + rutas de control: 2 passed
alembic: sin cambios
make check: 543 passed, 35 deselected
pre-commit: Passed
```

## Aislamiento de instancias (T065, T068)

- Dos `QdrantIndex` con `cut5-a`/`cut5-b`, el mismo `case_id` y el mismo servidor: cada uno recupera
  solo sus puntos de caso y su corpus público.
- Colecciones y alias incluyen el `instance_id`; la evidencia (`query_with_identity`) informa el
  namespace correcto y una generación real.
- Copia del marcador a otra ruta: `instance_namespace_mismatch`, sin escribir el marcador, sin crear
  colecciones y sin cambiar aliases.

## Coordinación entre procesos (T066)

`tests/integration/test_qdrant_lock_processes.py` crea procesos propios y los sincroniza con archivos
de señal y tiempos máximos, sin pausas arbitrarias.

- Proceso A adquiere `ingestion`; un segundo proceso intenta `rebuild` y recibe
  `ingestion_in_progress` (no adquiere el lock).
- Al terminar A normalmente, el lock queda libre y puede adquirirse.
- SIGKILL sobre el titular: el sistema operativo libera el lock; el archivo conserva el registro del
  propietario, pero `inspect_lock` devuelve `None` (no se interpreta como activo).
- El alias anterior sigue apuntando a la misma colección y la consulta devuelve el punto; después
  puede adquirirse el lock de ingesta.

## Integración del lock en los escritores (T067)

- `documents/service.py`: adquiere `ingestion` y lo mantiene hasta confirmar disponibilidad o marcar
  el fallo (`fd7a5be`).
- `retrieval/rebuild.py`: adquiere `rebuild` y publica el reporte dentro del lock.
- `ingest_corpus.py`/`prepare_demo.py`: ingestan por el servicio, por lo que usan el mismo lock.
- No se añadió otra primitiva ni un bloqueo global; los intentos usan `attempt_id` automático y el
  registro de propietario existente.

## Sin tablas ni migraciones (T069)

`git diff --stat -- alembic/` está vacío. Marcadores, locks y reportes viven en
`<SECGUARD_STORAGE_DIR>/qdrant-control/`, fuera de `storage/qdrant` (prueba
`tests/unit/test_qdrant_paths.py`). La prueba de persistencia de casos sigue en verde.

## Servidor real

Qdrant 1.20.0, dos namespaces exclusivos y storage temporal:

```text
case_a: ['1111…'] case_b: ['2222…']
public_a: ['3333…'] public_b: ['4444…']
evidence_instance: cut5-a generation: True
copy_mismatch: instance_namespace_mismatch
```

El servicio se detuvo con `make qdrant-down` (sin `-v`). No se modificó `storage/` ni `storage/demo`,
no se borraron datos de Chroma y no se usaron datos privados de Qualys.

## Interfaz

Sin cambios de interfaz ni de evidencia visible; no se repitió la revisión con Playwright.
