"""Authenticated private document library API."""

from __future__ import annotations

import hashlib
import hmac
import logging
import mimetypes
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from orinoco.db import (
    User,
    create_document,
    delete_document,
    get_database_path,
    get_document,
    get_user_by_id,
    initialise_database,
    list_documents,
)
from orinoco.documents.extract import MAX_UPLOAD_BYTES, extract_text
from orinoco.documents.storage import (
    document_storage_lock,
    remove_document_file,
    resolve_document_path,
    store_document,
)

router = APIRouter(prefix="/api/documents", tags=["documents"])
logger = logging.getLogger(__name__)


def _require_csrf(request: Request) -> None:
    """Require a valid CSRF token before changing a user's document collection."""
    expected = request.session.get("csrf_token")
    supplied = request.headers.get("x-csrf-token")
    if not isinstance(expected, str) or not isinstance(supplied, str) or not hmac.compare_digest(expected, supplied):
        raise HTTPException(status_code=403, detail="Refresh the page and try again.")


def _current_user(request: Request) -> User:
    """Resolve the active account from the signed request session."""
    user_id = request.session.get("user_id")
    if not isinstance(user_id, int):
        raise HTTPException(status_code=401, detail="Please sign in to continue.")
    database_path = get_database_path()
    initialise_database(database_path)
    user = get_user_by_id(user_id, database_path=database_path)
    if user is None or not user.active:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Please sign in to continue.")
    return user


def _safe_filename(filename: str | None) -> str:
    """Reduce an upload filename to a safe display name without trusting its path."""
    value = (filename or "upload").replace("\\", "/").split("/")[-1]
    value = "".join(character for character in value if character.isprintable() and character not in "\r\n")
    if not value or value in {".", ".."}:
        raise HTTPException(status_code=400, detail="A valid filename is required.")
    return value[:180]


async def _store_upload(file: UploadFile, *, user_id: int, scope: str) -> dict[str, object]:
    """Validate, extract and persist a document with private/shared ownership metadata."""
    filename = _safe_filename(file.filename)
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Documents are limited to 10 MiB.")
    try:
        extracted = await run_in_threadpool(extract_text, filename, data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    extension = Path(filename).suffix.lower()
    database_path = get_database_path()
    # Keep the file write and metadata insert atomic relative to backups/deletes.
    with document_storage_lock():
        stored_path = store_document(
            data,
            user_id=user_id if scope == "private" else None,
            scope=scope,
            extension=extension,
        )
        try:
            document_id = create_document(
                owner_user_id=user_id if scope == "private" else None,
                scope=scope,
                original_name=filename,
                stored_path=stored_path,
                file_type=extension.lstrip("."),
                size_bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
                extracted_text=extracted,
                database_path=database_path,
            )
        except Exception:
            try:
                remove_document_file(stored_path)
            except (OSError, ValueError):
                logger.exception("Could not clean up an unregistered document upload.")
            raise
    return {
        "id": document_id,
        "scope": scope,
        "original_name": filename,
        "file_type": extension.lstrip("."),
        "size_bytes": len(data),
    }


@router.get("")
async def get_documents(request: Request) -> dict[str, object]:
    """List the current user's private files and documents visible from the shared library."""
    user = _current_user(request)
    return {"documents": list_documents(user.id, database_path=get_database_path())}


@router.post("", status_code=201)
async def upload_private_document(
    request: Request,
    file: UploadFile = File(...),
) -> dict[str, object]:
    """Store a document privately under the authenticated user's account."""
    _require_csrf(request)
    user = _current_user(request)
    return {"document": await _store_upload(file, user_id=user.id, scope="private")}


@router.get("/{document_id}/download")
async def download_document(document_id: int, request: Request) -> FileResponse:
    """Download a document only when the current account is allowed to see it."""
    user = _current_user(request)
    document = get_document(
        user.id,
        document_id,
        allow_shared=True,
        database_path=get_database_path(),
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    try:
        path = resolve_document_path(str(document["stored_path"]))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Document not found.") from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Document file is missing.")
    media_type = mimetypes.guess_type(str(document["original_name"]))[0] or "application/octet-stream"
    return FileResponse(
        path,
        media_type=media_type,
        filename=str(document["original_name"]),
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.delete("/{document_id}")
async def remove_private_document(document_id: int, request: Request) -> dict[str, bool]:
    """Delete a private document only when the current account owns it."""
    _require_csrf(request)
    user = _current_user(request)
    document = get_document(
        user.id,
        document_id,
        allow_shared=False,
        database_path=get_database_path(),
    )
    if document is None or document["scope"] != "private":
        raise HTTPException(status_code=404, detail="Document not found.")
    stored_path = str(document["stored_path"])
    try:
        # Remove the original first. If storage cleanup fails, keep the DB row
        # visible so the owner can retry instead of silently orphaning private data.
        remove_document_file(stored_path)
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=500,
            detail="The document could not be removed from storage; it remains listed so you can retry.",
        ) from exc
    deleted_path = delete_document(
        user.id,
        document_id,
        allow_shared=False,
        database_path=get_database_path(),
    )
    if deleted_path is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"deleted": True}
