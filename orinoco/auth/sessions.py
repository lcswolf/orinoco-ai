"""Persistent signing secret and secure cookie settings."""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from fastapi import HTTPException, Request

from orinoco.db import User, get_database_path, get_user_by_id, initialise_database


def get_session_secret() -> str:
    """Load the configured signing secret or create a persistent, owner-readable secret file."""
    configured = os.environ.get("ORINOCO_SECRET_KEY")
    if configured:
        if len(configured) < 32:
            raise RuntimeError("ORINOCO_SECRET_KEY must contain at least 32 characters")
        return configured

    secret_path = Path(
        os.environ.get(
            "ORINOCO_SESSION_SECRET_PATH",
            str(get_database_path().parent / ".session_secret"),
        )
    )
    try:
        secret_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(
                secret_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
        except FileExistsError:
            secret = secret_path.read_text(encoding="utf-8").strip()
            if len(secret) < 32:
                raise RuntimeError("The persisted Orinoco session secret is invalid")
            return secret

        secret = secrets.token_urlsafe(48)
        with os.fdopen(descriptor, "w", encoding="utf-8") as secret_file:
            secret_file.write(secret)
            secret_file.flush()
            os.fsync(secret_file.fileno())
        try:
            secret_path.chmod(0o600)
        except OSError:
            pass
        return secret
    except OSError:
        if os.environ.get("ORINOCO_ENV", "development").lower() == "production":
            raise RuntimeError(
                "Could not create the persistent Orinoco session secret. "
                "Check the data directory permissions."
            )
        # Development and CI may not have the production data directory.
        # Sessions will reset whenever this development process restarts.
        return secrets.token_urlsafe(48)


def secure_cookie_enabled() -> bool:
    """Return whether session cookies must be marked Secure for HTTPS deployments."""
    value = os.environ.get("ORINOCO_COOKIE_SECURE", "true").strip().lower()
    return value not in {"0", "false", "no", "off"}



def get_session_user(request: Request, *, require_admin: bool = False) -> User:
    """Resolve a signed-in account and reject stale sessions after password or access changes."""
    user_id = request.session.get("user_id")
    session_version = request.session.get("session_version")
    if not isinstance(user_id, int) or not isinstance(session_version, int):
        request.session.clear()
        raise HTTPException(status_code=401, detail="Please sign in to continue.")

    database_path = get_database_path()
    initialise_database(database_path)
    user = get_user_by_id(user_id, database_path=database_path)
    if (
        user is None
        or not user.active
        or user.session_version != session_version
    ):
        # A password change, suspension/reactivation or other revocation makes
        # every older signed cookie invalid, even if the account is active again.
        request.session.clear()
        raise HTTPException(status_code=401, detail="Please sign in to continue.")

    if require_admin and user.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator access is required.")
    return user
