"""Administrator-only account management routes."""

from __future__ import annotations

import hmac

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from orinoco.db import (
    AccountError,
    User,
    create_user,
    get_database_path,
    get_user_by_id,
    initialise_database,
    list_users,
    set_user_active,
)

router = APIRouter(prefix="/api/admin", tags=["administration"])


class CreateUserRequest(BaseModel):
    """Validated fields required to create a standard user account."""
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=12, max_length=1024)


class UserStatusRequest(BaseModel):
    """Validated active/suspended state requested by an administrator."""
    active: bool


def _require_csrf(request: Request) -> None:
    """Reject state-changing browser requests without a valid session CSRF token."""
    expected = request.session.get("csrf_token")
    supplied = request.headers.get("x-csrf-token")
    if (
        not isinstance(expected, str)
        or not isinstance(supplied, str)
        or not hmac.compare_digest(expected, supplied)
    ):
        raise HTTPException(status_code=403, detail="Refresh the page and try again.")


def _require_admin(request: Request) -> User:
    """Require an authenticated, active administrator for this operation."""
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


def _user_response(user: User) -> dict[str, object]:
    """Convert an account into its safe public API representation."""
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "active": user.active,
        "created_at": user.created_at,
    }


@router.get("/users")
async def get_users(request: Request) -> dict[str, object]:
    """Return account summaries to administrators only."""
    _require_admin(request)
    return {
        "users": [
            _user_response(user)
            for user in list_users(database_path=get_database_path())
        ]
    }


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def add_user(
    payload: CreateUserRequest,
    request: Request,
) -> dict[str, object]:
    """Create a standard account after administrator and CSRF checks."""
    _require_csrf(request)
    _require_admin(request)
    try:
        user = create_user(
            payload.username,
            payload.password,
            role="user",
            database_path=get_database_path(),
        )
    except AccountError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"user": _user_response(user)}


@router.patch("/users/{user_id}")
async def update_user_status(
    user_id: int,
    payload: UserStatusRequest,
    request: Request,
) -> dict[str, bool]:
    """Suspend or reactivate another account without allowing self-lockout."""
    _require_csrf(request)
    admin = _require_admin(request)
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot suspend your own account.")
    try:
        updated = set_user_active(
            user_id,
            payload.active,
            database_path=get_database_path(),
        )
    except AccountError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not updated:
        raise HTTPException(status_code=404, detail="User not found.")
    return {"updated": True, "active": payload.active}
