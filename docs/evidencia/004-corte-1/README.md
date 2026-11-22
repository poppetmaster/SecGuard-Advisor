# Corte 1 — Infraestructura Qdrant, instancia y lock

**Fecha**: 2026-11-22 09:30–10:05 (America/Bogota, `-05`)
**Estado actual**: T001–T009 completadas. Docker Desktop 29.9.3 (aarch64) y Qdrant 1.20.0 verificados
en ejecución; el servicio de prueba se detuvo y el volumen se conservó.
**Rama**: `004-qdrant-vector-index`
**Alcance**: T001–T009 de `specs/004-qdrant-vector-index/tasks.md`. Preparación de infraestructura
local; Chroma sigue siendo el backend documental y no se modifica SQLite, documentos, casos,
conversaciones, Qualys ni archivos de Chroma.

## Entorno observado

- macOS arm64 (Apple Silicon), Python 3.14.6, `uv 0.13.0`.
- Docker Desktop 29.9.3, motor aarch64, contexto `desktop-linux`; `docker compose` 5.8.0.
- Las secciones «Reintento», «Tercera comprobación» y «Bloqueo histórico» registran intentos previos
  en los que el motor no estaba disponible. No describen el estado actual.

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

## Compose (T002) — histórico: verificación inicial bloqueada

`compose.qdrant.yml` fija `qdrant/qdrant:v1.20.0`, publica solo `127.0.0.1:6333` y `127.0.0.1:6334`,
monta `./storage/qdrant:/qdrant/storage` y usa `restart: unless-stopped`.

Validación disponible sin Docker (PyYAML del entorno, solo como comprobación puntual):

```text
compose YAML parse OK; image, ports, volume and restart match the plan
```

En esa comprobación inicial `docker compose config` no se ejecutó por ausencia del CLI; la validación
real se completó después (ver «Tercera comprobación» y «Cuarta comprobación»).

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

## Verificación arm64 y salud (T009) — histórico: bloqueo por motor

En esa comprobación inicial no se pudo ejecutar la verificación exigida porque el motor no estaba
disponible:

```text
$ docker manifest inspect qdrant/qdrant:v1.20.0
zsh: command not found: docker
$ make qdrant-up
make: docker: No such file or directory
$ curl -fsS http://127.0.0.1:6333/readyz
curl: (7) Failed to connect to 127.0.0.1 port 6333
```

Evidencia parcial de esa comprobación (registro público, solo lectura): la etiqueta `v1.20.0` existe
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

## Servicios y datos (verificación inicial)

- En la verificación inicial no se levantó ningún servicio porque el motor no estaba disponible. No
  hubo nada que detener y no se usó `down -v`.
- No se ejecutaron migraciones ni reconstrucciones de índices.
- No se modificó `storage/`, SQLite, Chroma ni datos del usuario.
- Las pruebas de instancia y marcador usan directorios temporales (`tmp_path`).

## Bloqueo histórico (resuelto el 2026-11-22 10:02)

Los intentos previos quedaron bloqueados primero por ausencia del CLI y después por ausencia del
motor. El bloqueo se resolvió al iniciar Docker Desktop; no se cambió la versión fijada ni el alcance.
La verificación final está en «Cuarta comprobación — T009 completado».

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

## Tercera comprobación (2026-11-22 09:47, America/Bogota)

El CLI de Docker ya está instalado mediante Homebrew:

```text
$ docker --version
Docker version 29.10.0, build fdd4b8e5da
$ docker compose version
Docker Compose version 5.8.0
```

El motor no está disponible: no existe `/var/run/docker.sock`, `docker info` falla con «no such file
or directory» y no hay Docker Desktop, Colima, Lima, OrbStack ni Rancher Desktop instalados. El
contexto `default` apunta al socket local. No se instaló ni se arrancó un motor, y no se modificó la
configuración global.

### T002 — completado

```text
$ docker compose -f compose.qdrant.yml config
name: secguard-advisor
services:
  qdrant:
    restart: unless-stopped
    container_name: secguard-qdrant
    image: qdrant/qdrant:v1.20.0
    volumes:
      - type: bind
        target: /qdrant/storage
    ports:
      - host_ip: 127.0.0.1, target: 6333, published: "6333", protocol: tcp
      - host_ip: 127.0.0.1, target: 6334, published: "6334", protocol: tcp
```

Salida 0. Imagen fijada, ambos puertos con `host_ip: 127.0.0.1` y volumen persistente
`./storage/qdrant` montado en `/qdrant/storage`.

### T009 — imagen verificada; arranque y salud bloqueados

```text
$ docker manifest inspect qdrant/qdrant:v1.20.0
mediaType: application/vnd.oci.image.index.v1+json
platforms: linux/amd64, linux/arm64
exit=0
```

```text
$ make qdrant-up
failed to connect to the docker API at unix:///var/run/docker.sock
make: *** [qdrant-up] Error 1
$ make qdrant-health
curl: (7) Failed to connect to 127.0.0.1 port 6333
make: *** [qdrant-health] Error 7
```

La imagen soporta arm64 y el compose es válido, pero sin motor no se puede arrancar el servicio ni
comprobar `/readyz`. No se inició ningún servicio, no hubo nada que detener y el volumen no se tocó.

### Comprobaciones de ID y namespace (T009)

Siguen cubiertas y en verde: ID inválido produce `instance_configuration_invalid` y el marcador
copiado a otra ruta produce `instance_namespace_mismatch` (25 pruebas unitarias de instancia). No se
repite aquí su salida para no duplicar la evidencia anterior.

### Estado

- T002: **completado** con `docker compose config`.
- T009: **bloqueado** por ausencia de motor; manifiesto arm64 ya verificado con el comando exigido.

## Cuarta comprobación — T009 completado (2026-11-22 10:02, America/Bogota)

Motor activo y arranque real del servicio fijado.

```text
$ docker info --format 'server={{.ServerVersion}} driver={{.Driver}} arch={{.Architecture}}'
server=29.9.3 driver=overlayfs arch=aarch64
$ docker context ls
desktop-linux *   Docker Desktop   unix:///Users/.../.docker/run/docker.sock
$ docker ps -a
(sin contenedores)
$ lsof -nP -iTCP:6333 -sTCP:LISTEN
(libre)
```

```text
$ make qdrant-up
Image qdrant/qdrant:v1.20.0 Pulled
Network secguard-advisor_default Created
Container secguard-qdrant Started
$ docker compose -f compose.qdrant.yml ps
secguard-qdrant   qdrant/qdrant:v1.20.0   Up   Less than a second   127.0.0.1:6333-6334->6333-6334/tcp
```

```text
$ make qdrant-health
all shards are ready
{"title":"qdrant - vector search engine","version":"1.20.0","commit":"222b2e44..."}
exit=0
$ curl -fsS -w "\nhttp=%{http_code}\n" http://127.0.0.1:6333/readyz
all shards are ready
http=200
```

Versión real del servidor: **1.20.0**, coherente con la imagen fijada. Puertos publicados:

```text
$ docker port secguard-qdrant
6333/tcp -> 127.0.0.1:6333
6334/tcp -> 127.0.0.1:6334
$ docker inspect secguard-qdrant --format '{{json .NetworkSettings.Ports}}'
{"6333/tcp":[{"HostIp":"127.0.0.1","HostPort":"6333"}],"6334/tcp":[{"HostIp":"127.0.0.1","HostPort":"6334"}]}
```

Detención controlada, sin `down -v`:

```text
$ make qdrant-down
Container secguard-qdrant Stopped
Container secguard-qdrant Removed
Network secguard-advisor_default Removed
$ docker ps -a
(sin contenedores)
$ lsof -nP -iTCP:6333 -sTCP:LISTEN
(libre)
$ ls storage/qdrant
aliases  collections  raft_state.json
```

El volumen se conservó. No se interrumpió ningún otro servicio: no había contenedores ni proyectos
Compose preexistentes. Las comprobaciones de ID y namespace siguen cubiertas por las 25 pruebas
unitarias de instancia (`instance_configuration_invalid` e `instance_namespace_mismatch`).

**T009 completado.**
