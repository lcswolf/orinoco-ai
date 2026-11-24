"""Authenticated endpoints for per-user response preferences."""

from __future__ import annotations

import hmac

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from orinoco.auth.sessions import get_session_user
from orinoco.db import get_database_path, get_user_preferences, update_user_preferences

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


class PreferencesRequest(BaseModel):
    """Whitelisted voice, tone and answer-detail choices for one account."""

    voice: str = Field(pattern="^(bright|calm|professional)$")
    tone: str = Field(pattern="^(friendly|direct|playful)$")
    answer_detail: str = Field(pattern="^(concise|balanced|detailed)$")


def _require_csrf(request: Request) -> None:
    """Require the signed-in session's CSRF token before changing preferences."""
    expected = request.session.get("csrf_token")
    supplied = request.headers.get("x-csrf-token")
    if (
        not isinstance(expected, str)
        or not isinstance(supplied, str)
        or not hmac.compare_digest(expected, supplied)
    ):
        raise HTTPException(status_code=403, detail="Refresh the page and try again.")


@router.get("")
async def read_preferences(request: Request) -> dict[str, str]:
    """Return only the signed-in user's own preference values."""
    user = get_session_user(request)
    return get_user_preferences(user.id, database_path=get_database_path())


@router.put("")
async def save_preferences(
    payload: PreferencesRequest,
    request: Request,
) -> dict[str, str]:
    """Update only the signed-in user's whitelisted response preferences."""
    _require_csrf(request)
    user = get_session_user(request)
    try:
        return update_user_preferences(
            user.id,
            voice=payload.voice,
            tone=payload.tone,
            answer_detail=payload.answer_detail,
            database_path=get_database_path(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
