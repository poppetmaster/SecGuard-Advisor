"""Identidad de instancia, namespace, marcador y lock de mantenimiento de Qdrant.

SQLite sigue siendo la fuente de verdad. Este módulo solo resuelve la identidad
lógica de la instancia, su marcador persistente y el lock compartido entre
procesos; no escribe documentos ni índices.
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from secguard_advisor.config import INSTANCE_ID_PATTERN

try:  # pragma: no cover - Windows queda fuera del objetivo declarado
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

MARKER_SCHEMA_VERSION = 1
OPERATIONS = frozenset({"ingestion", "rebuild"})
_MAX_OWNER_BYTES = 4096


class InstanceError(Exception):
    """Error de identidad, namespace o lock de instancia."""

    code = "instance_error"


class InstanceConfigurationError(InstanceError):
    """Identificador de instancia ausente o inválido."""

    code = "instance_configuration_invalid"


class InstanceNamespaceMismatch(InstanceError):
    """El marcador o el namespace no corresponden al almacenamiento actual."""

    code = "instance_namespace_mismatch"


class InstanceLockBusy(InstanceError):
    """La instancia ya tiene una operación activa."""

    code = "instance_lock_busy"

    def __init__(self, owner: LockOwner | None) -> None:
        self.owner = owner
        detail = f" ({owner.operation})" if owner is not None else ""
        super().__init__(f"La instancia ya tiene una operación activa{detail}.")


class LockUnreadable(InstanceError):
    """El lock existe pero su propietario no puede leerse o interpretarse."""

    code = "lock_unreadable"


@dataclass(frozen=True, slots=True)
class InstanceMarker:
    instance_id: str
    storage_fingerprint: str
    schema_version: int
    created_at: str


@dataclass(frozen=True, slots=True)
class LockOwner:
    operation: str
    attempt_id: str
    pid: int
    started_at: str


def _require_fcntl():
    if fcntl is None:  # pragma: no cover - Windows fuera del objetivo declarado
        raise InstanceConfigurationError(
            "El lock de instancia requiere flock; Windows no es un objetivo soportado."
        )
    return fcntl


def validate_instance_id(value: str | None) -> str:
    """Valida el slug de instancia y devuelve el valor normalizado."""
    if value is None or not INSTANCE_ID_PATTERN.fullmatch(value):
        raise InstanceConfigurationError(
            "SECGUARD_INSTANCE_ID ausente o inválido: se requiere un slug estable de "
            "3 a 40 caracteres en minúsculas, dígitos o guiones."
        )
    return value


def control_dir(storage_dir: Path) -> Path:
    """Directorio de control de la aplicación, fuera del volumen de Qdrant."""
    return Path(storage_dir) / "qdrant-control"


def marker_path(storage_dir: Path, instance_id: str) -> Path:
    return control_dir(storage_dir) / "instances" / f"{validate_instance_id(instance_id)}.json"


def lock_path(storage_dir: Path, instance_id: str) -> Path:
    return control_dir(storage_dir) / "locks" / f"{validate_instance_id(instance_id)}.lock"


def instance_prefix(instance_id: str) -> str:
    """Prefijo de namespace para colecciones, alias y reportes."""
    return f"secguard__{validate_instance_id(instance_id)}__"


def storage_fingerprint(storage_dir: Path, instance_id: str) -> str:
    """SHA-256 de la ruta canónica y el ID; no depende del contenido."""
    canonical = os.path.realpath(Path(storage_dir))
    material = f"{canonical}\0{validate_instance_id(instance_id)}".encode()
    return hashlib.sha256(material).hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _load_marker(path: Path) -> InstanceMarker:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return InstanceMarker(
            instance_id=str(payload["instance_id"]),
            storage_fingerprint=str(payload["storage_fingerprint"]),
            schema_version=int(payload["schema_version"]),
            created_at=str(payload["created_at"]),
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise InstanceNamespaceMismatch(
            "El marcador de instancia existe pero no puede interpretarse."
        ) from exc


def read_marker(storage_dir: Path, instance_id: str) -> InstanceMarker | None:
    path = marker_path(storage_dir, instance_id)
    if not path.exists():
        return None
    return _load_marker(path)


def ensure_marker(
    storage_dir: Path,
    instance_id: str,
    *,
    namespace_present: bool,
) -> InstanceMarker:
    """Registra o valida el marcador sin adoptar un namespace ajeno.

    ``namespace_present`` indica si el servidor ya contiene colecciones o alias
    de esta instancia. Un marcador ausente con namespace existente falla cerrado.
    """
    instance_id = validate_instance_id(instance_id)
    fingerprint = storage_fingerprint(storage_dir, instance_id)
    path = marker_path(storage_dir, instance_id)

    if path.exists():
        marker = _load_marker(path)
        if marker.instance_id != instance_id or marker.storage_fingerprint != fingerprint:
            raise InstanceNamespaceMismatch(
                "El marcador de instancia no coincide con el almacenamiento actual."
            )
        return marker

    if namespace_present:
        raise InstanceNamespaceMismatch(
            "Existe un namespace de instancia sin marcador; no se adopta automáticamente."
        )

    marker = InstanceMarker(
        instance_id=instance_id,
        storage_fingerprint=fingerprint,
        schema_version=MARKER_SCHEMA_VERSION,
        created_at=_utc_now(),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(
            {
                "instance_id": marker.instance_id,
                "storage_fingerprint": marker.storage_fingerprint,
                "schema_version": marker.schema_version,
                "created_at": marker.created_at,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)
    return marker


def _read_owner(fd: int) -> LockOwner | None:
    os.lseek(fd, 0, os.SEEK_SET)
    raw = os.read(fd, _MAX_OWNER_BYTES).strip()
    if not raw:
        return None
    try:
        payload = json.loads(raw.decode("utf-8"))
        return LockOwner(
            operation=str(payload["operation"]),
            attempt_id=str(payload["attempt_id"]),
            pid=int(payload["pid"]),
            started_at=str(payload["started_at"]),
        )
    except UnicodeDecodeError, ValueError, KeyError, TypeError:
        return None


def _write_owner(fd: int, owner: LockOwner) -> None:
    payload = json.dumps(
        {
            "operation": owner.operation,
            "attempt_id": owner.attempt_id,
            "pid": owner.pid,
            "started_at": owner.started_at,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    os.lseek(fd, 0, os.SEEK_SET)
    os.ftruncate(fd, 0)
    os.write(fd, payload)


@contextmanager
def acquire_instance_lock(
    storage_dir: Path,
    instance_id: str,
    operation: str,
    *,
    attempt_id: str | None = None,
) -> Iterator[LockOwner]:
    """Adquiere el lock exclusivo de la instancia y registra su propietario."""
    fcntl_module = _require_fcntl()
    if operation not in OPERATIONS:
        raise InstanceConfigurationError(f"Operación de lock desconocida: {operation!r}.")
    path = lock_path(storage_dir, instance_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl_module.flock(fd, fcntl_module.LOCK_EX | fcntl_module.LOCK_NB)
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN}:
                raise InstanceLockBusy(_read_owner(fd)) from exc
            raise
        owner = LockOwner(
            operation=operation,
            attempt_id=attempt_id or uuid.uuid4().hex,
            pid=os.getpid(),
            started_at=_utc_now(),
        )
        _write_owner(fd, owner)
        try:
            yield owner
        finally:
            with suppress(OSError):
                os.ftruncate(fd, 0)
            with suppress(OSError):
                fcntl_module.flock(fd, fcntl_module.LOCK_UN)
    finally:
        os.close(fd)


def lock_conflict_code(owner: LockOwner | None) -> str:
    """Código de error para una ingesta que encuentra el lock ocupado."""
    if owner is not None and owner.operation == "rebuild":
        return "reconstruction_in_progress"
    return "ingestion_in_progress"


def inspect_lock(storage_dir: Path, instance_id: str) -> LockOwner | None:
    """Sondea el lock sin crear, truncar ni modificar archivos.

    Devuelve el propietario solo si el lock está tomado por un proceso vivo.
    Los metadatos residuales de un lock libre se ignoran.
    """
    fcntl_module = _require_fcntl()
    path = lock_path(storage_dir, instance_id)
    try:
        fd = os.open(path, os.O_RDONLY)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise LockUnreadable(f"No se puede leer el lock de instancia: {exc.strerror}.") from exc

    try:
        try:
            fcntl_module.flock(fd, fcntl_module.LOCK_EX | fcntl_module.LOCK_NB)
        except OSError as exc:
            if exc.errno not in {errno.EACCES, errno.EAGAIN}:
                raise
            owner = _read_owner(fd)
            if owner is None:
                raise LockUnreadable(
                    "El lock está tomado pero su registro de propietario falta o es ilegible."
                ) from exc
            return owner
        with suppress(OSError):
            fcntl_module.flock(fd, fcntl_module.LOCK_UN)
        return None
    finally:
        os.close(fd)
