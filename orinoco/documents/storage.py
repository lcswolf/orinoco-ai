"""Private file storage for uploaded Orinoco documents."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

DEFAULT_DOCUMENT_ROOT = Path(
    os.environ.get("ORINOCO_DOCUMENTS_PATH", "/home/container/data/documents")
)


def get_document_root() -> Path:
    """Return the configured root directory for private and shared document files."""
    return Path(os.environ.get("ORINOCO_DOCUMENTS_PATH", str(DEFAULT_DOCUMENT_ROOT)))


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
