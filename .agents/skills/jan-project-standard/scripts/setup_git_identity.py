#!/usr/bin/env python3
"""Configura la identidad Git automática vía ``includeIf`` (macOS y Windows).

Escribe (o solo imprime) un perfil de identidad y lo enlaza desde ``~/.gitconfig``
para que todo repositorio bajo una carpeta use automáticamente un nombre, un
correo y una llave SSH concretos.

Pensado para el **Perfil B** del skill ``jan-project-standard``: usuarios que
**no** son Jan y necesitan su propia identidad (alumnos, compañeros, etc.).

Ejemplos::

    # macOS / Linux
    python3 setup_git_identity.py --name "Pedro Pérez" --email pedro@example.com \\
        --key ~/.ssh/id_ed25519 --dir ~/Repos/personal --platform mac

    # Windows (PowerShell)
    python3 setup_git_identity.py --name "Pedro Pérez" --email pedro@example.com \\
        --key C:/Users/pedro/.ssh/id_ed25519 --dir C:/Users/pedro/Repos --platform windows

    # Solo mostrar la configuración, sin escribir nada
    python3 setup_git_identity.py --name "Pedro" --email p@e.com --dir ~/Repos --print

Es **seguro**: respalda ``~/.gitconfig`` antes de modificarlo y es idempotente.
"""

from __future__ import annotations

import argparse
import datetime as dt
import shutil
import subprocess
import sys
from pathlib import Path


def to_posix(path: str) -> str:
    """Normaliza separadores a ``/`` (válido en macOS y Windows para Git)."""
    return path.replace("\\", "/")


def normalize_dir(raw: str, platform: str) -> str:
    """Devuelve el patrón de carpeta listo para ``gitdir[:/i]``."""
    value = to_posix(raw.strip())
    if value.startswith("~"):
        value = str(Path(value).expanduser())
        value = to_posix(value)
    if not value.endswith("/"):
        value += "/"
    return value


def normalize_profile(raw: str) -> Path:
    return Path(raw).expanduser()


def includeif_prefix(platform: str) -> str:
    # En Windows se usa gitdir/i: (comparación insensible a mayúsculas).
    return "gitdir/i" if platform == "windows" else "gitdir"


def build_profile(name: str, email: str, key: str | None) -> str:
    lines = ["[user]", f"\tname = {name}", f"\temail = {email}"]
    if key:
        ssh_command = f"ssh -i {to_posix(key)} -o IdentitiesOnly=yes"
        lines += ["", "[core]", f"\tsshCommand = {ssh_command}"]
    return "\n".join(lines) + "\n"


def build_include_block(directory: str, profile: Path, platform: str) -> str:
    prefix = includeif_prefix(platform)
    profile_posix = to_posix(str(profile))
    return f'[includeIf "{prefix}:{directory}"]\n\tpath = {profile_posix}\n'


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def backup(path: Path) -> Path | None:
    if not path.exists():
        return None
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = path.with_name(path.name + f".bak-{stamp}")
    shutil.copyfile(path, dest)
    return dest


def maybe_keygen(key: str | None, email: str, enabled: bool) -> None:
    if not key or not enabled:
        return
    key_path = Path(key).expanduser()
    if key_path.exists():
        print(f"[ssh] la llave ya existe: {key_path}")
        return
    key_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["ssh-keygen", "-t", "ed25519", "-C", email, "-f", str(key_path), "-N", ""],
            check=True,
        )
        print(f"[ssh] llave generada: {key_path}")
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"[ssh] no se pudo generar la llave: {exc}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Configura la identidad Git automática vía includeIf.",
    )
    parser.add_argument("--name", required=True, help="Nombre completo para los commits.")
    parser.add_argument("--email", required=True, help="Correo para los commits.")
    parser.add_argument("--dir", required=True, help="Carpeta de proyectos a asociar.")
    parser.add_argument("--key", help="Llave SSH privada (p. ej. ~/.ssh/id_ed25519).")
    parser.add_argument(
        "--platform",
        choices=["mac", "linux", "windows", "auto"],
        default="auto",
        help="Sistema operativo (por defecto: auto).",
    )
    parser.add_argument(
        "--gitconfig",
        default="~/.gitconfig",
        help="Archivo gitconfig principal (por defecto: ~/.gitconfig).",
    )
    parser.add_argument(
        "--profile",
        default="~/.gitconfig-personal",
        help="Archivo de perfil de identidad (por defecto: ~/.gitconfig-personal).",
    )
    parser.add_argument("--ssh-keygen", action="store_true", help="Genera la llave SSH si falta.")
    parser.add_argument(
        "--print",
        dest="print_only",
        action="store_true",
        help="Solo imprime los bloques; no escribe nada.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Muestra qué haría sin escribir.")
    parser.add_argument("--force", action="store_true", help="Sobrescribe el perfil de identidad.")
    return parser


def resolve_platform(value: str) -> str:
    if value != "auto":
        return value
    return "windows" if sys.platform.startswith("win") else "mac"


def main() -> int:
    args = build_parser().parse_args()
    platform = resolve_platform(args.platform)

    directory = normalize_dir(args.dir, platform)
    profile = normalize_profile(args.profile).resolve()
    gitconfig = normalize_profile(args.gitconfig).resolve()

    profile_block = build_profile(args.name, args.email, args.key)
    include_block = build_include_block(directory, profile, platform)

    print(f"\n▶ Identidad Git automática ({platform})")
    print(f"  Nombre    : {args.name} <{args.email}>")
    print(f"  Carpeta   : {directory}")
    print(f"  Perfil    : {profile}")
    print(f"  gitconfig : {gitconfig}")
    if args.key:
        print(f"  Llave SSH : {to_posix(args.key)}")

    if args.print_only:
        print("\n── ~/.gitconfig-personal ─────────────────────────────")
        print(profile_block)
        print("── añadir a ~/.gitconfig ─────────────────────────────")
        print(include_block)
        print("── comandos manuales ─────────────────────────────────")
        print(f"  mkdir -p {profile.parent}")
        print(f"  # escribe el perfil y añade el bloque includeIf a {gitconfig}")
        print(f"  cd {args.dir}")
        print("  git config --show-origin --get user.email")
        print("  ssh -T git@github.com")
        return 0

    if args.dry_run:
        print("\n[dry-run] no se escribirá nada.")
        return 0

    maybe_keygen(args.key, args.email, args.ssh_keygen)

    existing = read_text(gitconfig)
    already = directory in existing

    if already and not args.force:
        print("\n[gitconfig] el bloque includeIf para esta carpeta ya existe; nada que hacer.")
    else:
        if gitconfig.exists():
            dest = backup(gitconfig)
            if dest:
                print(f"[gitconfig] respaldo: {dest}")
        profile.parent.mkdir(parents=True, exist_ok=True)
        if profile.exists() and not args.force:
            print(f"[perfil] ya existe y no se sobrescribe: {profile}")
        else:
            profile.write_text(profile_block, encoding="utf-8")
            print(f"[perfil] escrito: {profile}")
        with gitconfig.open("a", encoding="utf-8") as handle:
            if existing and not existing.endswith("\n"):
                handle.write("\n")
            handle.write("\n")
            handle.write(include_block)
        print(f"[gitconfig] bloque includeIf añadido: {gitconfig}")

    print("\n── Siguientes pasos ──────────────────────────────────")
    if args.key and not Path(args.key).expanduser().with_suffix(".pub").exists():
        print(f"  1. Sube la llave pública a GitHub: {to_posix(args.key)}.pub")
        print("     GitHub → Settings → SSH and GPG keys → New SSH key")
    else:
        print("  1. Verifica que tu llave SSH esté registrada en GitHub.")
    print(f"  2. cd {args.dir}")
    print("  3. git config --show-origin --get user.email")
    print("  4. ssh -T git@github.com")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
