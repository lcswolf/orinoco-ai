"""Administrator-only shared document library API."""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from orinoco.db import (
    User,
    create_document,
    delete_document,
    get_database_path,
    get_user_by_id,
    initialise_database,
    list_documents,
)
from orinoco.documents.routes import _require_csrf, _store_upload
from orinoco.documents.storage import remove_document_file

router = APIRouter(prefix="/api/admin/shared-documents", tags=["administration"])


def _require_admin(request: Request) -> User:
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
    _require_admin(request)
    return {"documents": list_documents(0, shared_only=True, database_path=get_database_path())}


@router.post("", status_code=201)
async def upload_shared_document(
    request: Request,
    file: UploadFile = File(...),
) -> dict[str, object]:
    _require_csrf(request)
    admin = _require_admin(request)
    return {"document": await _store_upload(file, user_id=admin.id, scope="shared")}


@router.delete("/{document_id}")
async def delete_shared_document(document_id: int, request: Request) -> dict[str, bool]:
    _require_csrf(request)
    _require_admin(request)
    stored_path = delete_document(
        0,
        document_id,
        allow_shared=True,
        database_path=get_database_path(),
    )
    if stored_path is None:
        raise HTTPException(status_code=404, detail="Shared document not found.")
    remove_document_file(stored_path)
    return {"deleted": True}
