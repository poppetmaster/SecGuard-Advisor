# Contexto para agentes LLM

El estándar asume que en el proyecto trabajan agentes (OpenCode, Antigravity, Copilot CLI,
Claude Code, etc.). Para que no adivinen, el repositorio incluye archivos de contexto
versionados.

## `AGENTS.md`

Ubicado en la **raíz** del proyecto. Es el equivalente operativo del `CONSTITUTION.md`
para agentes: apunta a la constitución y resume las reglas que el agente debe respetar.

Contenido recomendado:

1. Encabezado: qué es el proyecto y hacia dónde apunta.
2. Enlace a `CONSTITUTION.md` como fuente única de verdad.
3. **Búsqueda de código con `tgrep`** (si está disponible).
4. Flujo diario (commit + push) y convención de commits.
5. Punteros a `Makefile`, tests y estructura.

> **Regla:** `AGENTS.md` **no duplica** la constitución; la enlaza. Si un dato cambia, se
> actualiza en la constitución y `AGENTS.md` lo refleja o lo referencia.

## Regla OpenCode: `tgrep`

Archivo `.opencode/rules/tgrep.md` (versionado). Configura al agente para preferir
[`tgrep`](https://github.com/microsoft/tgrep) (índice de trigramas) sobre `grep`/`find`
en búsquedas de código.

```bash
tgrep -- "patrón" .            # búsqueda regex (usa -- antes del patrón)
tgrep -F -- "simbolo" .        # coincidencia literal
tgrep -t py -- "def " .        # filtrar por tipo de archivo
tgrep -g "src/**" -- "kw" .    # filtrar por ruta
tgrep -l -- "import torch" .   # listar archivos
tgrep index .                  # (re)indexar
tgrep serve . &                # daemon en segundo plano
```

- Índice en `.tgrep/` (ignorado por Git).
- Es **opcional**: si `tgrep` no está instalado, se usa `grep` normal.

El archivo vive como **regla de OpenCode** para que la preferencia se aplique de forma
automática en cada sesión.

## Identidad Git automática (configuración local, no trackear)

`~/.gitconfig` (global):

```ini
[includeIf "gitdir:~/Repos/"]
    path = ~/.gitconfig-personal
```

`~/.gitconfig-personal`:

```ini
[user]
    name = <Tu Nombre>
    email = <tu-correo>
[core]
    sshCommand = ssh -i ~/.ssh/id_ed25519 -o IdentitiesOnly=yes
```

**Efecto:** los repos bajo esa carpeta usan automáticamente el nombre, el correo y la llave
SSH correctos. No requiere `gh`, variables de entorno ni flags por proyecto. Configuración y
perfiles (macOS/Windows) en [`git-identity.md`](git-identity.md).

> Esto es configuración de la **máquina**, no del repositorio: se documenta en la
> constitución como nota y **nunca** se versiona un archivo con secretos.

## Remotos

Preferir **SSH**:

```text
origin  git@github.com:<tu-usuario>/<repo>.git (fetch)
origin  git@github.com:<tu-usuario>/<repo>.git (push)
```

## Buenas prácticas de contexto

- Un dato, un lugar: la constitución manda; los demás archivos la referencian.
- Mantén `AGENTS.md` corto (una pantalla). Si crece, muévelo a `docs/` y enlázalo.
- Registra en la constitución los comandos y gotchas que un agente debe conocer para no
  repetir errores (puertos ocupados, dependencias con *pins* especiales, etc.).
- Evita secretos embebidos: usa `.env` (ignorado) y `"{env:VAR}"` en configs de MCP.
