# 004 — Último resultado (Corte 1)

**Fecha**: 2026-11-22 09:30–10:05 (America/Bogota, `-05`)
**Rama**: `004-qdrant-vector-index`
**Alcance ejecutado**: Corte 1, T001–T009. No se inició T010 ni ninguna tarea posterior.
**Backend documental**: Chroma sigue siendo el backend activo. Qdrant queda preparado como
infraestructura local; no se sustituyó el índice ni se modificó SQLite, Chroma, casos, documentos,
conversaciones o Qualys.

## Commits de esta pasada

| Commit | Contenido |
|---|---|
| `73f304d` | `docs: reconcile 004 planning and record analysis reports` (planificación revisada y análisis) |
| `3cd264a` | `feat(deps): pin qdrant-client 1.20.0` |
| `62cd7c0` | `feat(config): add instance and qdrant settings` |
| `3febecf` | `feat(retrieval): add instance marker namespace and lock` |
| `8356acc` | `feat(qdrant): add local compose and maintenance targets` |

Sin push ni publicación.

## Estado de T001–T009

| Tarea | Estado | Evidencia |
|---|---|---|
| T001 dependencia fijada | **Completada** | `qdrant-client==1.20.0`; `uv lock --check` resuelve 139 paquetes; `uv sync --locked` instala; Chroma conservado. |
| T002 compose | **Abierta (implementada, verificación bloqueada)** | `compose.qdrant.yml` creado y YAML válido; falta `docker compose config` porque Docker no está instalado. |
| T003 configuración | **Completada** | Campos y validación en `config.py`; 10 pruebas de configuración en verde. |
| T004 `.env.example` | **Completada** | Variables documentadas, sin credenciales ni rutas privadas. |
| T005 targets Makefile | **Completada** | `make -n` reproducible y `make help` lista los tres targets. |
| T006 pruebas de instancia (RED) | **Completada** | RED observado: `ImportError: cannot import name 'instance'`. |
| T007 instancia, namespace, marcador y lock | **Completada** | 25 pruebas de instancia en verde; fingerprint estable ante cambios de contenido; sondeo sin escrituras. |
| T008 contrato de despliegue | **Completada** | 5 pruebas de contrato en verde. |
| T009 arm64 y `/readyz` | **Bloqueada** | Docker ausente: `docker manifest inspect` no disponible, `make qdrant-up` falla y `/readyz` no responde. Evidencia parcial: la etiqueta `v1.20.0` existe y su índice incluye `linux/arm64`. |

Resumen: **7 completadas, 1 implementada sin verificación (T002), 1 bloqueada (T009)**.

## Archivos modificados o creados

- `pyproject.toml`, `uv.lock`: dependencia fijada.
- `src/secguard_advisor/config.py`: instancia, URL y timeout de Qdrant; `chroma_dir` conservado.
- `.env.example`: variables de Qdrant documentadas.
- `Makefile`: `qdrant-up`, `qdrant-down`, `qdrant-health` con `##`.
- `compose.qdrant.yml`: imagen fijada, loopback, volumen y reinicio.
- `src/secguard_advisor/retrieval/instance.py`: slug, namespace, marcador/fingerprint, registro,
  lock con propietario y sondeo de solo lectura.
- `tests/unit/test_qdrant_instance.py`, `tests/unit/test_config.py`,
  `tests/contract/test_qdrant_deployment.py`.
- `AGENTS.md`, `specs/004-qdrant-vector-index/tasks.md`, esta página, el handoff y
  `docs/evidencia/004-corte-1/README.md`.

## Comandos y resultados observados

```text
uv lock --check                      → Resolved 139 packages in 6ms
uv sync --locked                     → qdrant-client==1.20.0 instalado
uv run pytest tests/unit/test_qdrant_instance.py tests/unit/test_config.py → 35 passed
uv run pytest tests/contract/test_qdrant_deployment.py → 5 passed
make -n qdrant-up qdrant-down qdrant-health → comandos reproducibles
make -s help | grep qdrant → tres targets listados
compose YAML parse (PyYAML) → imagen, puertos, volumen y reinicio correctos
make check                           → 452 passed, 35 deselected
uv run pre-commit run --all-files    → todas las comprobaciones Passed
docker manifest inspect qdrant/qdrant:v1.20.0 → command not found
make qdrant-up                       → docker: No such file or directory
curl http://127.0.0.1:6333/readyz    → connection refused (exit 7)
Registro público de la imagen        → tag v1.20.0; plataformas linux/amd64 y linux/arm64
```

Línea base previa a los cambios: `make check` = `417 passed, 35 deselected`.

## Limitaciones y bloqueo real

- Docker no está instalado en el equipo. Por eso no se ejecutaron `docker compose config`,
  `docker manifest inspect`, `make qdrant-up`, `/readyz` ni la detención controlada del servicio.
- No se levantó ningún servicio; no hubo nada que detener y no se usó `down -v`.
- No se ejecutaron migraciones ni reconstrucciones; no se tocó almacenamiento del usuario.
- Las pruebas de instancia y lock usan directorios temporales.
- No se sustituyó la versión fijada para evitar el bloqueo.

## Siguiente paso

1. En un equipo con Docker: ejecutar `docker compose -f compose.qdrant.yml config` (T002) y la
   verificación de T009 (`docker manifest inspect`, `make qdrant-up`, `/readyz`, `make qdrant-down`
   conservando el volumen). Marcar T002 y T009 solo con esa evidencia.
2. Con el Corte 1 cerrado, iniciar el Corte 2 (T010–T042) en una tarea posterior. No se inició aquí.

No se ejecutó `/speckit.implement` ni se declaró Qdrant como backend implementado o aceptado.
