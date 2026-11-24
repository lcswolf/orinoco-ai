"""Private file storage for uploaded Orinoco documents."""

from __future__ import annotations

import os

try:
    import fcntl
except ImportError:  # Windows development uses the msvcrt locking fallback.
    fcntl = None
from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

DEFAULT_DOCUMENT_ROOT = Path(
    os.environ.get("ORINOCO_DOCUMENTS_PATH", "/home/container/data/documents")
)


def get_document_root() -> Path:
    """Return the configured root directory for private and shared document files."""
    return Path(os.environ.get("ORINOCO_DOCUMENTS_PATH", str(DEFAULT_DOCUMENT_ROOT)))


@contextmanager
def document_storage_lock() -> Iterator[None]:
    """Serialize document file/DB changes with backup snapshots across processes.

    The lock file lives beside the document root, not inside it, so it is not
    included in document backups. An OS-level file lock works across Orinoco processes
    sharing the same persistent Pterodactyl data directory.
    """
    root = get_document_root()
    root.parent.mkdir(parents=True, exist_ok=True)
    lock_path = root.parent / ".documents.lock"
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(lock_path, flags, 0o600)
    with os.fdopen(descriptor, "r+b") as lock_file:
        try:
            os.fchmod(lock_file.fileno(), 0o600)
        except (AttributeError, OSError):
            # Windows filesystems may not expose POSIX permission bits.
            pass
        if fcntl is not None:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        else:
            # msvcrt locks a byte range, so ensure the lock file has one byte.
            import msvcrt

            lock_file.seek(0, os.SEEK_END)
            if lock_file.tell() == 0:
                lock_file.write(b"\0")
                lock_file.flush()
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)


def store_document(data: bytes, *, user_id: int | None, scope: str, extension: str) -> str:
    """Write an uploaded document under a random name with restrictive directory and file permissions."""
    if scope not in {"private", "shared"}:
        raise ValueError("document scope must be private or shared")
    if scope == "private" and user_id is None:
        raise ValueError("private documents require a user ID")
    if extension.lower() not in {".txt", ".md", ".pdf", ".docx", ".xlsx", ".pptx"}:
        raise ValueError("unsupported document extension")

    root = get_document_root()
    folder = Path("shared") if scope == "shared" else Path("private") / str(user_id)
    directory = root / folder
    directory.mkdir(parents=True, exist_ok=True)
    try:
        root.chmod(0o700)
        directory.chmod(0o700)
    except OSError:
        pass
    relative = folder / f"{uuid4().hex}{extension.lower()}"
    target = root / relative
    temporary = target.with_suffix(target.suffix + ".tmp")
    with temporary.open("xb") as file_handle:
        file_handle.write(data)
        file_handle.flush()
        os.fsync(file_handle.fileno())
    os.replace(temporary, target)
    try:
        target.chmod(0o600)
    except OSError:
        pass
    return relative.as_posix()


def resolve_document_path(relative_path: str) -> Path:
    """Resolve a stored relative path and reject traversal outside the document root."""
    root = get_document_root().resolve()
    relative = Path(relative_path)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ValueError("invalid document storage path")
    candidate = root / relative
    if candidate.is_symlink():
        raise ValueError("symbolic links are not valid document storage paths")
    candidate = candidate.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("invalid document storage path") from exc
    return candidate


def remove_document_file(relative_path: str) -> None:
    """Remove a stored file, surfacing cleanup failures so the DB row can be retained."""
    path = resolve_document_path(relative_path)
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        # Callers must keep the document record when the original file cannot
        # be removed, allowing the owner or administrator to retry cleanup.
        raise OSError("Could not securely remove the stored document file.") from exc
