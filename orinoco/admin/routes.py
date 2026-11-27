"""Administrator-only account management routes."""

from __future__ import annotations

import hmac

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import Response

from orinoco.auth.sessions import get_session_user
from pydantic import BaseModel, Field

from orinoco.identity import get_identity, save_pending_identity
from orinoco.db import (
    AccountError,
    User,
    create_user,
    get_assistant_persona,
    get_database_path,
    get_user_by_id,
    initialise_database,
    list_users,
    set_user_active,
    update_assistant_persona,
)

router = APIRouter(prefix="/api/admin", tags=["administration"])


class CreateUserRequest(BaseModel):
    """Validated fields required to create a standard user account."""
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=12, max_length=1024)


class UserStatusRequest(BaseModel):
    """Validated active/suspended state requested by an administrator."""
    active: bool


class AssistantIdentityRequest(BaseModel):
    """Complete administrator-managed identity profile."""
    name: str = Field(max_length=80)
    creator: str = Field(max_length=120)
    organisation: str = Field(max_length=120)
    purpose: str = Field(max_length=500)
    background: str = Field(max_length=1000)
    introduction: str = Field(max_length=500)
    project_url: str = Field(max_length=2048)
    core_personality: str = Field(max_length=1200)
    humour_level: int = Field(ge=0, le=100, strict=True)
    warmth: int = Field(ge=0, le=100, strict=True)
    formality: int = Field(ge=0, le=100, strict=True)
    patience: int = Field(ge=0, le=100, strict=True)
    response_length: str
    language_policy: str
    advanced_guidance: str = Field(max_length=2000)

class AssistantPersonaRequest(BaseModel):
    """Administrator-managed core persona and humour level."""
    core_persona: str = Field(min_length=1, max_length=2000)
    humour_level: int = Field(ge=0, le=100, strict=True)


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
    """Require a signed-in administrator whose session has not been revoked."""
    return get_session_user(request, require_admin=True)


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


@router.get("/identity")
async def read_assistant_identity(request: Request) -> dict[str, object]:
    """Return active and pending identity metadata to administrators only."""
    _require_admin(request)
    return get_identity(database_path=get_database_path())


@router.put("/identity")
async def save_assistant_identity(payload: AssistantIdentityRequest, request: Request) -> dict[str, object]:
    """Save a validated identity profile for activation on the next restart."""
    _require_csrf(request)
    _require_admin(request)
    try:
        return save_pending_identity(payload.model_dump(), database_path=get_database_path())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.get("/persona")
async def read_assistant_persona(request: Request) -> dict[str, object]:
    """Return the global assistant persona to administrators only."""
    _require_admin(request)
    return get_assistant_persona(database_path=get_database_path())


@router.put("/persona")
async def save_assistant_persona(
    payload: AssistantPersonaRequest,
    request: Request,
) -> dict[str, object]:
    """Save the global assistant persona after administrator and CSRF checks."""
    _require_csrf(request)
    _require_admin(request)
    try:
        return update_assistant_persona(
            core_persona=payload.core_persona,
            humour_level=payload.humour_level,
            database_path=get_database_path(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/diagnostics")
async def read_diagnostics(request: Request) -> dict[str, object]:
    """Run bounded, read-only operational checks for administrators."""
    _require_admin(request)
    from orinoco.diagnostics import run_diagnostics

    return await run_diagnostics()



@router.post("/diagnostics/support-bundle")
async def download_support_bundle(request: Request) -> Response:
    """Generate a bounded, privacy-filtered support ZIP for administrators."""
    _require_csrf(request)
    _require_admin(request)
    from orinoco.diagnostics import build_support_bundle

    try:
        bundle = await build_support_bundle()
    except (OSError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail="The support bundle could not be generated safely.") from exc
    return Response(
        content=bundle,
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="orinoco-support-bundle.zip"',
            "Cache-Control": "no-store, private",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )
