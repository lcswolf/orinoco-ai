"""Login, logout and current-account API routes."""

from __future__ import annotations

import hmac
import secrets

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from orinoco.db import (
    User,
    authenticate_user,
    get_database_path,
    get_user_by_id,
    initialise_database,
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=1, max_length=1024)


def _require_csrf(request: Request) -> None:
    expected = request.session.get("csrf_token")
    supplied = request.headers.get("x-csrf-token")
    if (
        not isinstance(expected, str)
        or not isinstance(supplied, str)
        or not hmac.compare_digest(expected, supplied)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your security token has expired. Refresh the page and try again.",
        )


def _public_user(user: User) -> dict[str, object]:
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
    }


@router.get("/csrf")
async def csrf_token(request: Request) -> dict[str, str]:
    token = request.session.get("csrf_token")
    if not isinstance(token, str):
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return {"csrf_token": token}


@router.post("/login")
async def login(payload: LoginRequest, request: Request) -> dict[str, object]:
    _require_csrf(request)
    initialise_database(get_database_path())
    user = authenticate_user(
        payload.username,
        payload.password,
        database_path=get_database_path(),
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The username or password was not recognised.",
        )

    # Rotate the session after authentication to prevent session fixation.
    request.session.clear()
    request.session["user_id"] = user.id
    request.session["csrf_token"] = secrets.token_urlsafe(32)
    return {"authenticated": True, "user": _public_user(user)}


@router.get("/me")
async def current_account(request: Request) -> dict[str, object]:
    user_id = request.session.get("user_id")
    if not isinstance(user_id, int):
        return {"authenticated": False}

    initialise_database(get_database_path())
    user = get_user_by_id(user_id, database_path=get_database_path())
    if user is None or not user.active:
        request.session.clear()
        return {"authenticated": False}

    return {"authenticated": True, "user": _public_user(user)}


@router.post("/logout")
async def logout(request: Request) -> dict[str, bool]:
    _require_csrf(request)
    request.session.clear()
    return {"authenticated": False}
