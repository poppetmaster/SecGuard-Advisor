# Identidad Git automática (`includeIf`)

Configura Git para que cada repositorio que viva bajo una carpeta concreta use
**automáticamente** un nombre, un correo y una llave SSH —sin `gh auth` por proyecto y sin
flags manuales—. Se implementa con `includeIf` en `~/.gitconfig`.

> ⚠️ **Es configuración local de la máquina.** Nunca se commitea al repositorio: vive en la
> constitución solo **como nota** (nunca como archivo del proyecto).
>
> 🙋 **Solo se aplica si el usuario lo pide.** Esta sección tiene dos perfiles. Identifica
> cuál corresponde y **pide explícitamente los datos** (nombre, correo, llave y carpeta)
> antes de escribir nada. No inventes rutas ni correos.

---

## Perfil A — Ejemplo: configuración del autor de la skill

> Es solo un **ejemplo real** de cómo se ve un perfil funcionando. Cualquier otro usuario
> debe seguir el **Perfil B** con sus propios datos.

La carpeta canónica del autor es `~/Desktop/Repositorios/personal/`. `~/.gitconfig` incluye:

```ini
[includeIf "gitdir:~/Desktop/Repositorios/personal/"]
    path = ~/.gitconfig-personal
```

`~/.gitconfig-personal`:

```ini
[user]
    name = Jan Polanco V.
    email = hamsomp3@gmail.com
[core]
    sshCommand = ssh -i ~/.ssh/id_ed25519 -o IdentitiesOnly=yes
```

**Efecto:** todo repo bajo esa carpeta usa automáticamente `Jan Polanco V.`,
`hamsomp3@gmail.com` y la llave `~/.ssh/id_ed25519`. Preferir remotos **SSH**
(`git@github.com:hamsomp3/<repo>.git`); HTTPS puede resolver con el token de otra cuenta.

Verificación:

```bash
cd ~/Desktop/Repositorios/personal
git config --show-origin --get user.email   # -> hamsomp3@gmail.com (desde ~/.gitconfig-personal)
ssh -T git@github.com                        # -> Hi hamsomp3!
```

---

## Perfil B — NO soy Jan (alumno, compañero, otro usuario)

Cuando el usuario **no es Jan**, no tiene sentido reutilizar la ruta fija
`~/Desktop/Repositorios/personal/`. Hay que configurar **su** identidad en **su** carpeta
de proyectos, en **su** sistema operativo.

### Paso 0 · Preguntar al usuario (obligatorio)

Antes de tocar `~/.gitconfig`, reúne:

| Dato | Ejemplo | Notas |
|------|---------|-------|
| Nombre completo | `Pedro Pérez` | El que aparecerá en los commits. |
| Correo | `pedro@example.com` | De preferencia el correo de su cuenta GitHub. |
| Llave SSH | `~/.ssh/id_ed25519` | Ruta a la llave privada (se puede generar). |
| Carpeta de proyectos | `~/Repos/personal` (mac) · `C:/Users/pedro/Repos` (win) | Todo repo dentro usará esa identidad. |

> Si el usuario no tiene llave SSH, genera una:
> `ssh-keygen -t ed25519 -C "pedro@example.com"` (acepta la ruta por defecto) y luego sube
> `~/.ssh/id_ed25519.pub` a **GitHub → Settings → SSH and GPG keys → New SSH key**.

### Opción rápida — script incluido

El script escribe (o solo imprime) la configuración correcta para macOS y Windows:

```bash
# macOS / Linux
python3 <SKILL_DIR>/scripts/setup_git_identity.py \
  --name "Pedro Pérez" --email pedro@example.com \
  --key ~/.ssh/id_ed25519 --dir ~/Repos/personal --platform mac

# Windows (PowerShell)
python3 .\scripts\setup_git_identity.py `
  --name "Pedro Pérez" --email pedro@example.com `
  --key C:/Users/pedro/.ssh/id_ed25519 --dir C:/Users/pedro/Repos --platform windows
```

Opciones: `--print` (solo muestra los bloques, **no escribe nada**), `--dry-run`,
`--ssh-keygen` (genera la llave si falta), `--force` (sobrescribe el perfil),
`--profile <ruta>` (por defecto `~/.gitconfig-personal`).

### Opción manual — macOS / Linux

```bash
# 1. Crear el perfil de identidad
cat > ~/.gitconfig-personal <<'EOF'
[user]
    name = Pedro Pérez
    email = pedro@example.com
[core]
    sshCommand = ssh -i ~/.ssh/id_ed25519 -o IdentitiesOnly=yes
EOF

# 2. Enlazarlo desde ~/.gitconfig (usa >> para no destruir tu configuración)
cat >> ~/.gitconfig <<'EOF'

[includeIf "gitdir:~/Repos/personal/"]
    path = ~/.gitconfig-personal
EOF

# 3. Verificar (desde dentro de la carpeta)
cd ~/Repos/personal
git config --show-origin --get user.email   # -> pedro@example.com
ssh -T git@github.com                        # -> Hi pedro!
```

### Opción manual — Windows

En Windows usa **rutas con `/`** (no `\`) dentro del `.gitconfig`, y el prefijo
`gitdir/i:` (comparación **i**nsensible a mayúsculas/minúsculas, típico de Windows).
También conviene escribir la ruta **completa** del perfil (sin `~`).

```ini
# En C:/Users/pedro/.gitconfig
[includeIf "gitdir/i:C:/Users/pedro/Repos/**"]
    path = C:/Users/pedro/.gitconfig-personal
```

```ini
# En C:/Users/pedro/.gitconfig-personal
[user]
    name = Pedro Pérez
    email = pedro@example.com
[core]
    sshCommand = ssh -i C:/Users/pedro/.ssh/id_ed25519 -o IdentitiesOnly=yes
```

Verificación en **PowerShell**:

```powershell
cd C:\Users\pedro\Repos
git config --show-origin --get user.email      # -> pedro@example.com
ssh -T git@github.com                           # -> Hi pedro!
```

> Con Git Bash, `~/.gitconfig` y `~/.gitconfig-personal` apuntan a
> `C:/Users/pedro/` automáticamente.

### Notas y gotchas (ambos sistemas)

- **Orden importa:** en `~/.gitconfig`, un `includeIf` **posterior** gana sobre el bloque
  `[user]` global. Coloca el `includeIf` **después** de tu `[user]` global.
- **Patrón de carpeta:** termina la ruta con `/` (macOS) o `/**` (Windows) según lo
  necesites; `gitdir:` casa por prefijo de directorio. Usa `gitdir/i:` si el sistema de
  archivos distingue mayúsculas de forma inconsistente (Windows).
- **Llave SSH:** `-o IdentitiesOnly=yes` evita que SSH pruebe todas tus llaves y falle por
  "too many authentication failures".
- **HTTPS vs SSH:** si `git push` por HTTPS falla con `Repository not found`, cambia el
  remoto a SSH: `git remote set-url origin git@github.com:<usuario>/<repo>.git`.
- **No versionar:** `~/.gitconfig` y `~/.gitconfig-personal` **jamás** entran al repo.

---

## Cómo decide el agente

1. ¿El usuario pide configurar una carpeta **existente** con datos ya definidos (el patrón
   del Perfil A)? → úsalo como referencia, pero **confirma sus datos** antes de escribir.
2. En cualquier otro caso, si el usuario pide identidad automática → **Perfil B**: primero
   pregunta nombre, correo, llave y carpeta; luego usa el script o los bloques manuales de su SO.
3. ¿No lo pide? → No toques `~/.gitconfig`; limítate a documentarlo como nota en la
   constitución del proyecto.
