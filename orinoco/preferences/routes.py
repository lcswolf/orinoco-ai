"""Authenticated endpoints for per-user response preferences."""

from __future__ import annotations

import hmac

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from orinoco.auth.sessions import get_session_user
from orinoco.db import get_database_path, get_user_preferences, update_user_preferences

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


class PreferencesRequest(BaseModel):
    """Whitelisted language, voice, tone and answer-detail choices for one account."""

    voice: str = Field(pattern="^(bright|calm|professional)$")
    tone: str = Field(pattern="^(friendly|direct|playful)$")
    answer_detail: str = Field(pattern="^(concise|balanced|detailed)$")
    language: str | None = Field(default=None, pattern="^(auto|en|cy)$")
    auto_save_memories: bool | None = None


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
async def read_preferences(request: Request) -> dict[str, object]:
    """Return only the signed-in user's own preference values."""
    user = get_session_user(request)
    return get_user_preferences(user.id, database_path=get_database_path())


@router.put("")
async def save_preferences(
    payload: PreferencesRequest,
    request: Request,
) -> dict[str, object]:
    """Update only the signed-in user's whitelisted response preferences."""
    _require_csrf(request)
    user = get_session_user(request)
    try:
        current = get_user_preferences(user.id, database_path=get_database_path())
        return update_user_preferences(
            user.id,
            voice=payload.voice,
            tone=payload.tone,
            answer_detail=payload.answer_detail,
            language=(current["language"] if payload.language is None else payload.language),
            auto_save_memories=(current["auto_save_memories"] if payload.auto_save_memories is None else payload.auto_save_memories),
            database_path=get_database_path(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
