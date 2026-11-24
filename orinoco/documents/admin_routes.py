"""Administrator-only shared document library API."""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
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
from orinoco.documents.routes import _require_csrf, _store_upload
from orinoco.documents.storage import remove_document_file

router = APIRouter(prefix="/api/admin/shared-documents", tags=["administration"])


def _require_admin(request: Request) -> User:
    """Require an active administrator before accessing the shared library controls."""
    user_id = request.session.get("user_id")
    if not isinstance(user_id, int):
        raise HTTPException(status_code=401, detail="Please sign in to continue.")
    database_path = get_database_path()
    initialise_database(database_path)
    user = get_user_by_id(user_id, database_path=database_path)
    if user is None or not user.active:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Please sign in to continue.")
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator access is required.")
    return user


@router.get("")
async def get_shared_documents(request: Request) -> dict[str, object]:
    """List documents in the administrator-managed shared reference library."""
    _require_admin(request)
    return {"documents": list_documents(0, shared_only=True, database_path=get_database_path())}


@router.post("", status_code=201)
async def upload_shared_document(
    request: Request,
    file: UploadFile = File(...),
) -> dict[str, object]:
    """Validate, extract and store a document in the shared read-only library."""
    _require_csrf(request)
    admin = _require_admin(request)
    return {"document": await _store_upload(file, user_id=admin.id, scope="shared")}


@router.delete("/{document_id}")
async def delete_shared_document(document_id: int, request: Request) -> dict[str, bool]:
    """Remove a shared document after an administrator ownership check."""
    _require_csrf(request)
    _require_admin(request)
    document = get_document(
        0,
        document_id,
        allow_shared=True,
        database_path=get_database_path(),
    )
    if document is None or document["scope"] != "shared":
        raise HTTPException(status_code=404, detail="Shared document not found.")
    with document_storage_lock():
        try:
            # Keep the shared-library row visible if the original file cannot be removed.
            remove_document_file(str(document["stored_path"]))
        except (OSError, ValueError) as exc:
            raise HTTPException(
                status_code=500,
                detail="The shared document could not be removed from storage; it remains listed so you can retry.",
            ) from exc
        stored_path = delete_document(
            0,
            document_id,
            allow_shared=True,
            database_path=get_database_path(),
        )
        if stored_path is None:
            raise HTTPException(status_code=404, detail="Shared document not found.")
    return {"deleted": True}
