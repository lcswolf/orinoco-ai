"""Login, logout and current-account API routes."""

from __future__ import annotations

import hmac
import secrets
import time
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from orinoco.db import (
    User,
    authenticate_user,
    change_user_password,
    get_database_path,
    get_user_by_id,
    initialise_database,
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])
MAX_LOGIN_FAILURES = 5
LOGIN_WINDOW_SECONDS = 15 * 60
_login_failures: dict[str, deque[float]] = defaultdict(deque)


class LoginRequest(BaseModel):
    """Validated username and password supplied to the login endpoint."""
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=1, max_length=1024)


class PasswordChangeRequest(BaseModel):
    """Validated current and replacement password fields."""
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=12, max_length=1024)


def _require_csrf(request: Request) -> None:
    """Reject browser mutations that do not carry the session's CSRF token."""
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


def _check_login_rate(username: str) -> None:
    """Apply a short in-process delay after repeated failed login attempts."""
    now = time.monotonic()
    failures = _login_failures[username]
    while failures and now - failures[0] > LOGIN_WINDOW_SECONDS:
        failures.popleft()
    if len(failures) >= MAX_LOGIN_FAILURES:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many unsuccessful sign-in attempts. Please wait and try again.",
            headers={"Retry-After": str(LOGIN_WINDOW_SECONDS)},
        )


def _public_user(user: User) -> dict[str, object]:
    """Return account details without exposing credential or session data."""
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
    }


@router.get("/csrf")
async def csrf_token(request: Request) -> dict[str, str]:
    """Create or return the CSRF token associated with the current session."""
    token = request.session.get("csrf_token")
    if not isinstance(token, str):
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return {"csrf_token": token}


@router.post("/login")
async def login(payload: LoginRequest, request: Request) -> dict[str, object]:
    """Authenticate an active account and establish its signed browser session."""
    _require_csrf(request)
    username = payload.username.strip().lower()
    _check_login_rate(username)
    initialise_database(get_database_path())
    user = authenticate_user(
        username,
        payload.password,
        database_path=get_database_path(),
    )
    if user is None:
        _login_failures[username].append(time.monotonic())
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The username or password was not recognised.",
        )

    _login_failures.pop(username, None)
    # Rotate the session after authentication to prevent session fixation.
    request.session.clear()
    request.session["user_id"] = user.id
    request.session["csrf_token"] = secrets.token_urlsafe(32)
    return {"authenticated": True, "user": _public_user(user)}


@router.get("/me")
async def current_account(request: Request) -> dict[str, object]:
    """Return the currently authenticated account, if the session is valid."""
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
    """Invalidate the current browser session and clear its cookie."""
    _require_csrf(request)
    request.session.clear()
    return {"authenticated": False}



@router.post("/password")
async def change_password(
    """Verify the current password and update the authenticated account's hash."""
    payload: PasswordChangeRequest,
    request: Request,
) -> dict[str, bool]:
    """Verify the current password and update the authenticated account's hash."""
    _require_csrf(request)
    user_id = request.session.get("user_id")
    if not isinstance(user_id, int):
        raise HTTPException(status_code=401, detail="Please sign in to continue.")

    initialise_database(get_database_path())
    try:
        changed = change_user_password(
            user_id,
            payload.current_password,
            payload.new_password,
            database_path=get_database_path(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if not changed:
        raise HTTPException(
            status_code=400,
            detail="The current password was not accepted.",
        )

    request.session.clear()
    request.session["user_id"] = user_id
    request.session["csrf_token"] = secrets.token_urlsafe(32)
    return {"changed": True}
