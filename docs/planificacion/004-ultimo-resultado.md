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
| `475c4b7` | `docs: record cut 1 evidence and status` |
| `95f19c6` | `docs: recheck cut 1 docker availability` |
| `2be3ccb` | `docs: complete T002 and record docker engine blocker` |
| `07e9ac4` | `docs: complete T009 with live qdrant health check` |

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
| T009 arm64 y `/readyz` | **Completada** | Motor Docker Desktop 29.9.3 (aarch64); imagen con `linux/arm64`; `make qdrant-up` arranca; `/readyz` responde 200 con «all shards are ready»; versión real 1.20.0; puertos solo loopback; `make qdrant-down` conserva el volumen. |

Resumen: **9 de 9 completadas**.

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
uv run pytest (instancia + config)   → 35 passed
uv run pytest (contrato despliegue)  → 5 passed
make -n qdrant-up qdrant-down qdrant-health → comandos reproducibles
make -s help | grep qdrant           → tres targets listados
make check                           → 452 passed, 35 deselected
uv run pre-commit run --all-files    → todas las comprobaciones Passed
docker compose config                → válido (imagen, loopback, volumen)
docker manifest inspect              → linux/amd64 y linux/arm64
docker info                          → server=29.9.3 arch=aarch64
make qdrant-up                       → contenedor secguard-qdrant Started
make qdrant-health                   → all shards are ready; version 1.20.0; exit 0
curl /readyz                         → 200 (all shards are ready)
docker port                          → 127.0.0.1:6333 y 127.0.0.1:6334
make qdrant-down                     → contenedor y red eliminados; volumen conservado
```

Línea base previa a los cambios: `make check` = `417 passed, 35 deselected`.
Los intentos fallidos por CLI o motor ausentes quedan documentados como historial en
`docs/evidencia/004-corte-1/README.md`; no son limitaciones vigentes.

## Limitaciones vigentes

- Chroma sigue siendo el backend documental; Qdrant es infraestructura local preparada, no una
  sustitución del índice.
- No se ejecutaron migraciones ni reconstrucciones y no se tocó SQLite, Chroma ni los datos.
- Las pruebas de instancia y lock usan directorios temporales.
- No queda ningún bloqueo abierto del Corte 1.

## Cierre del Corte 1 (2026-11-22 10:02)

Motor activo: Docker Desktop 29.9.3, `arch=aarch64`, contexto `desktop-linux`. Sin contenedores ni
proyectos Compose preexistentes y puertos 6333/6334 libres antes de empezar.

```text
$ make qdrant-up
Image qdrant/qdrant:v1.20.0 Pulled
Container secguard-qdrant Started
$ make qdrant-health
all shards are ready
{"title":"qdrant - vector search engine","version":"1.20.0",...}
$ curl http://127.0.0.1:6333/readyz
all shards are ready (http=200)
$ docker port secguard-qdrant
6333/tcp -> 127.0.0.1:6333
6334/tcp -> 127.0.0.1:6334
$ make qdrant-down
(contenedor y red eliminados; sin down -v)
$ ls storage/qdrant
aliases  collections  raft_state.json
```

La versión real del servidor coincide con la imagen fijada. El volumen se conservó, no se interrumpió
ningún servicio ajeno y no se tocó SQLite, Chroma ni los datos de la aplicación. Los bloqueos
anteriores por CLI y motor ausentes quedan como historial en
`docs/evidencia/004-corte-1/README.md`.

## Siguiente paso

Corte 1 cerrado. Iniciar el Corte 2 (T010–T042) en una tarea posterior y con autorización explícita.
No se inició T010 en esta pasada.

No se ejecutó `/speckit.implement` ni se declaró Qdrant como backend implementado o aceptado.
