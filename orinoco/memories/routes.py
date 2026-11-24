"""Private, per-user memory review and management API."""

from __future__ import annotations

import hmac

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from orinoco.db import User, get_database_path, get_user_by_id, initialise_database
from orinoco.memory.store import add_memory, delete_memory, list_memories, update_memory

router = APIRouter(prefix="/api/memories", tags=["memories"])


class MemoryRequest(BaseModel):
    content: str = Field(min_length=1, max_length=1000)

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("memory must not be blank")
        return value


def _require_csrf(request: Request) -> None:
    expected = request.session.get("csrf_token")
    supplied = request.headers.get("x-csrf-token")
    if not isinstance(expected, str) or not isinstance(supplied, str) or not hmac.compare_digest(expected, supplied):
        raise HTTPException(status_code=403, detail="Refresh the page and try again.")


def _current_user(request: Request) -> User:
    user_id = request.session.get("user_id")
    if not isinstance(user_id, int):
        raise HTTPException(status_code=401, detail="Please sign in to continue.")
    path = get_database_path()
    initialise_database(path)
    user = get_user_by_id(user_id, database_path=path)
    if user is None or not user.active:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Please sign in to continue.")
    return user


@router.get("")
async def get_memories(request: Request) -> dict[str, object]:
    user = _current_user(request)
    return {"memories": list_memories(user.id)}


@router.post("", status_code=201)
async def add_memory_route(payload: MemoryRequest, request: Request) -> dict[str, object]:
    _require_csrf(request)
    user = _current_user(request)
    try:
        memory = add_memory(user.id, payload.content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"id": memory["id"], "content": memory["content"], "source": "manual"}


@router.patch("/{memory_id}")
async def edit_memory(memory_id: int, payload: MemoryRequest, request: Request) -> dict[str, bool]:
    _require_csrf(request)
    user = _current_user(request)
    try:
        updated = update_memory(user.id, memory_id, payload.content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not updated:
        raise HTTPException(status_code=404, detail="Memory not found.")
    return {"updated": True}


@router.delete("/{memory_id}")
async def remove_memory(memory_id: int, request: Request) -> dict[str, bool]:
    _require_csrf(request)
    user = _current_user(request)
    if not delete_memory(user.id, memory_id):
        raise HTTPException(status_code=404, detail="Memory not found.")
    return {"deleted": True}
