# Corte 1 — Infraestructura Qdrant, instancia y lock

**Fecha**: 2026-11-22 09:30–10:05 (America/Bogota, `-05`)
**Rama**: `004-qdrant-vector-index`
**Alcance**: T001–T009 de `specs/004-qdrant-vector-index/tasks.md`. Preparación de infraestructura
local; Chroma sigue siendo el backend documental y no se modifica SQLite, documentos, casos,
conversaciones, Qualys ni archivos de Chroma.

## Entorno observado

- macOS arm64 (Apple Silicon), Python 3.14.6, `uv 0.13.0`.
- Docker **no instalado**: `docker` y `docker compose` no existen en el `PATH`. Esto bloquea las
  comprobaciones que dependen del motor (T002 parcial y T009).

## Dependencias (T001) — completado

```text
$ uv lock
Added qdrant-client v1.20.0
$ uv lock --check
Resolved 139 packages in 6ms
$ uv sync --locked
 + qdrant-client==1.20.0
$ grep -n "qdrant-client" pyproject.toml
    "qdrant-client==1.20.0",
```

`langchain-chroma` y `chromadb` siguen declarados. No se retiró ninguna dependencia.

## Compose (T002) — implementado, verificación bloqueada

`compose.qdrant.yml` fija `qdrant/qdrant:v1.20.0`, publica solo `127.0.0.1:6333` y `127.0.0.1:6334`,
monta `./storage/qdrant:/qdrant/storage` y usa `restart: unless-stopped`.

Validación disponible sin Docker (PyYAML del entorno, solo como comprobación puntual):

```text
compose YAML parse OK; image, ports, volume and restart match the plan
```

`docker compose -f compose.qdrant.yml config` **no se ejecutó**: Docker no está instalado. La tarea
permanece abierta hasta ejecutar esa comprobación en un equipo con Docker.

## Configuración e `.env.example` (T003, T004) — completado

- `config.py`: `SECGUARD_INSTANCE_ID` (slug opcional, validado), `SECGUARD_QDRANT_URL`,
  `SECGUARD_QDRANT_TIMEOUT_SECONDS`; `chroma_dir` se conserva.
- `.env.example`: variables documentadas con valores locales; sin credenciales ni rutas privadas.
- Pruebas: 10 pasan en `tests/unit/test_config.py`, incluidas ID válido, ID ausente/inválido, URL
  inválida y valores por defecto.

## Makefile (T005) — completado

```text
$ make -n qdrant-up qdrant-down qdrant-health
docker compose -f compose.qdrant.yml up -d
docker compose -f compose.qdrant.yml down
curl -fsS http://127.0.0.1:6333/readyz
curl -fsS http://127.0.0.1:6333/
$ make -s help | grep qdrant
  qdrant-down          Detiene el servidor Qdrant conservando el volumen
  qdrant-health        Comprueba /readyz y muestra la versión del servidor Qdrant
  qdrant-up            Levanta el servidor Qdrant local con el compose fijado
```

## Instancia, namespace, marcador y lock (T006, T007) — completado

Implementado en `src/secguard_advisor/retrieval/instance.py`:

- Validación de slug y composición de namespace `secguard__<instance_id>__`.
- Marcador en `<SECGUARD_STORAGE_DIR>/qdrant-control/instances/<id>.json` con fingerprint
  SHA-256 de la ruta canónica combinada con el ID; no depende del contenido.
- Reglas de registro: crea en primer uso; falla cerrado si el marcador falta y el namespace existe,
  si el ID no coincide o si el fingerprint no corresponde.
- Lock de archivo con registro de propietario `{operation, attempt_id, pid, started_at}` y sondeo de
  solo lectura que no crea, trunca ni modifica archivos; metadatos residuales con lock libre se ignoran.

Secuencia observada:

```text
$ uv run pytest tests/unit/test_qdrant_instance.py tests/unit/test_config.py
# antes de implementar instance.py:
E   ImportError: cannot import name 'instance' from 'secguard_advisor.retrieval'
# después:
35 passed
```

## Contrato de despliegue (T008) — completado

`tests/contract/test_qdrant_deployment.py`: 5 pruebas pasan. Verifican imagen fijada, puertos
loopback, volumen, `.env.example`, targets visibles en `make help`, namespace y que Chroma sigue
declarado en este corte.

## Verificación arm64 y salud (T009) — bloqueado

No se pudo ejecutar la comprobación exigida porque Docker no está instalado:

```text
$ docker manifest inspect qdrant/qdrant:v1.20.0
zsh: command not found: docker
$ make qdrant-up
make: docker: No such file or directory
$ curl -fsS http://127.0.0.1:6333/readyz
curl: (7) Failed to connect to 127.0.0.1 port 6333
```

Evidencia parcial del registro público (solo lectura, sin Docker): la etiqueta `v1.20.0` existe
(publicada 2026-10-21) y su índice incluye `linux/amd64` y `linux/arm64`. Esto no sustituye
`docker manifest inspect` ni la comprobación de `/readyz`.

## Fallos de configuración observados

```text
SECGUARD_INSTANCE_ID="Bad Id" → value_error: slug de 3 a 40 caracteres en minúsculas, dígitos o guiones
marcador copiado a otra ruta → instance_namespace_mismatch: el marcador no coincide con el almacenamiento actual
```

## Puertas de calidad

```text
$ make check
452 passed, 35 deselected
$ uv run pre-commit run --all-files
Todas las comprobaciones: Passed
```

Antes de los cambios, `make check` registró `417 passed, 35 deselected`.

## Servicios y datos

- No se levantó ningún servicio: Docker no está disponible. No hubo nada que detener y no se usó
  `down -v`.
- No se ejecutaron migraciones ni reconstrucciones de índices.
- No se modificó `storage/`, SQLite, Chroma ni datos del usuario.
- Las pruebas de instancia y marcador usan directorios temporales (`tmp_path`).

## Bloqueo real

`T002` y `T009` quedan abiertos únicamente por la ausencia de Docker en el equipo. Falta:

1. `docker compose -f compose.qdrant.yml config` (T002).
2. `docker manifest inspect qdrant/qdrant:v1.20.0`, `make qdrant-up`, `curl /readyz` y detención con
   `make qdrant-down` conservando el volumen (T009).

No se sustituyó la versión fijada ni se cambió el alcance para evitar el bloqueo.

## Reintento de verificación (2026-11-22 09:32, America/Bogota)

Se repitió la comprobación de disponibilidad de Docker antes de ejecutar T002/T009.

Búsqueda realizada, sin modificar configuración global:

```text
PATH incluye /usr/local/bin y /opt/homebrew/bin
which -a docker docker-compose        → no encontrados
/Applications                          → sin Docker, OrbStack, Rancher Desktop ni Podman
/usr/local/bin/docker                  → no existe
/opt/homebrew/bin/docker               → no existe
~/.docker/bin, ~/.orbstack/bin, ~/.rd/bin → no existen
procesos docker/orbstack/colima        → ninguno
launchctl                              → ninguna entrada
```

Ejecución de las comprobaciones exigidas:

```text
$ docker compose -f compose.qdrant.yml config
zsh: command not found: docker
$ docker manifest inspect qdrant/qdrant:v1.20.0
zsh: command not found: docker
$ make qdrant-up
make: docker: No such file or directory
$ make qdrant-health
curl: (7) Failed to connect to 127.0.0.1 port 6333
```

No es un problema de PATH: no hay motor ni CLI instalados. No se instaló Docker ni se modificó la
configuración del sistema.

Comprobaciones estáticas repetidas:

```text
compose: qdrant/qdrant:v1.20.0
puertos: 127.0.0.1:6333:6333, 127.0.0.1:6334:6334
volumen: ./storage/qdrant:/qdrant/storage
restart: unless-stopped
registro de imagen: linux/amd64 y linux/arm64
pruebas: 40 passed (instancia, configuración y contrato de despliegue)
```

Resultado: T002 y T009 continúan abiertas. No se arrancó ningún servicio, no hubo nada que detener y
no se tocó el volumen. No se cambió la versión fijada.
