# 004 — Último resultado (Corte 1)

**Fecha**: 2026-11-22 09:30–09:50 (America/Bogota, `-05`)
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
| T002 compose | **Completada** | `docker compose -f compose.qdrant.yml config` valida: imagen `v1.20.0`, `host_ip: 127.0.0.1` en 6333/6334, volumen persistente y reinicio. |
| T003 configuración | **Completada** | Campos y validación en `config.py`; 10 pruebas de configuración en verde. |
| T004 `.env.example` | **Completada** | Variables documentadas, sin credenciales ni rutas privadas. |
| T005 targets Makefile | **Completada** | `make -n` reproducible y `make help` lista los tres targets. |
| T006 pruebas de instancia (RED) | **Completada** | RED observado: `ImportError: cannot import name 'instance'`. |
| T007 instancia, namespace, marcador y lock | **Completada** | 25 pruebas de instancia en verde; fingerprint estable ante cambios de contenido; sondeo sin escrituras. |
| T008 contrato de despliegue | **Completada** | 5 pruebas de contrato en verde. |
| T009 arm64 y `/readyz` | **Bloqueada** | `docker manifest inspect` confirma `linux/arm64`; `make qdrant-up` falla por ausencia de motor (sin `/var/run/docker.sock`) y `/readyz` no responde. |

Resumen: **8 completadas, 1 bloqueada (T009)**.

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

## Reintento de verificación (2026-11-22 09:32)

Se volvió a comprobar Docker antes de ejecutar T002/T009:

- `which -a docker docker-compose`: no encontrados; el `PATH` ya incluye `/usr/local/bin` y
  `/opt/homebrew/bin`.
- Sin aplicaciones Docker, OrbStack, Rancher Desktop ni Podman en `/Applications`; sin procesos ni
  entradas de `launchctl`.
- `docker compose config`, `docker manifest inspect`, `make qdrant-up` y `make qdrant-health` fallan
  porque el comando `docker` no existe. No es un problema de PATH.
- Comprobaciones estáticas repetidas: compose fijado en `v1.20.0`, puertos solo loopback, volumen
  `./storage/qdrant`; el registro de la imagen confirma `linux/amd64` y `linux/arm64`; 40 pruebas
  pasan.

No se instaló Docker ni se modificó la configuración global. T002 y T009 siguen abiertas. No se
arrancó ningún servicio y no se tocó el volumen.

## Tercera comprobación (2026-11-22 09:47)

El CLI de Docker quedó disponible por Homebrew (`docker 29.10.0`, `docker compose 5.8.0`), pero el
motor no está instalado: no existe `/var/run/docker.sock`, `docker info` falla y no hay Docker
Desktop, Colima, Lima, OrbStack ni Rancher Desktop.

- **T002 completado**: `docker compose config` valida imagen, loopback y volumen.
- **T009 parcial**: `docker manifest inspect qdrant/qdrant:v1.20.0` confirma `linux/amd64` y
  `linux/arm64`. `make qdrant-up` falla por falta de motor y `make qdrant-health` no conecta a 6333.
- No se instaló ni arrancó un motor, no se inició ningún servicio y no se tocó el volumen.

## Siguiente paso

1. Arrancar un motor Docker local (Docker Desktop, Colima u otro) en un equipo que lo tenga. Con el
   motor activo: `make qdrant-up`, `make qdrant-health`, comprobar `/readyz` y `make qdrant-down`
   conservando el volumen. Marcar T009 solo con esa evidencia.
2. Con el Corte 1 cerrado, iniciar el Corte 2 (T010–T042) en una tarea posterior. No se inició aquí.

No se ejecutó `/speckit.implement` ni se declaró Qdrant como backend implementado o aceptado.
