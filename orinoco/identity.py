"""Versioned, administrator-managed Orinoco identity profiles.

Identity text is style/context only. Protected application guardrails remain
separate and are assembled by the chat route after this profile.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from urllib.parse import urlsplit

from orinoco.db import _database, get_database_path

DEFAULT_IDENTITY = {
    "name": "Orinoco",
    "creator": "",
    "organisation": "",
    "purpose": "A friendly, helpful personal AI assistant.",
    "background": "",
    "introduction": "I'm Orinoco, your private personal AI assistant.",
    "project_url": "",
    "core_personality": "Friendly, practical, curious, patient and encouraging.",
    "humour_level": 65,
    "warmth": 75,
    "formality": 35,
    "patience": 80,
    "response_length": "balanced",
    "language_policy": "follow_user",
    "advanced_guidance": "",
}

_TEXT_LIMITS = {
    "name": 80, "creator": 120, "organisation": 120, "purpose": 500,
    "background": 1000, "introduction": 500, "project_url": 2048,
    "core_personality": 1200, "advanced_guidance": 2000,
}
_ENUMS = {
    "response_length": {"concise", "balanced", "detailed"},
    "language_policy": {"follow_user", "welsh_default", "english_default"},
}
_SLIDERS = {"humour_level", "warmth", "formality", "patience"}


def _valid_project_url(value: str) -> bool:
    """Accept absolute HTTPS URLs with a hostname and no embedded credentials."""
    try:
        parsed = urlsplit(value)
        # Accessing .port also validates malformed and out-of-range port numbers.
        _ = parsed.port
        return (
            parsed.scheme.lower() == "https"
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
        )
    except ValueError:
        return False


def validate_identity(payload: dict[str, object]) -> dict[str, object]:
    """Validate a complete profile; reject unknown keys and unsafe URL schemes."""
    if not isinstance(payload, dict) or set(payload) != set(DEFAULT_IDENTITY):
        raise ValueError("Identity profile must include exactly the supported fields.")
    result: dict[str, object] = {}
    for key, maximum in _TEXT_LIMITS.items():
        value = payload[key]
        if not isinstance(value, str) or len(value.strip()) > maximum:
            raise ValueError(f"{key} must be text no longer than {maximum} characters.")
        cleaned = value.strip()
        if key in {"name", "purpose", "core_personality"} and not cleaned:
            raise ValueError(f"{key} cannot be blank.")
        if key == "project_url" and cleaned and not _valid_project_url(cleaned):
            raise ValueError("Project URL must be a valid absolute HTTPS URL without embedded credentials.")
        result[key] = cleaned
    for key, choices in _ENUMS.items():
        value = payload[key]
        if value not in choices:
            raise ValueError(f"Unsupported {key} value.")
        result[key] = value
    for key in _SLIDERS:
        value = payload[key]
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
            raise ValueError(f"{key} must be a whole number from 0 to 100.")
        result[key] = value
    return result


def _ensure_table(database_path) -> None:
    with _database(database_path) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS assistant_identity (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                active_json TEXT NOT NULL,
                pending_json TEXT,
                active_version INTEGER NOT NULL DEFAULT 1,
                pending_version INTEGER,
                updated_at TEXT NOT NULL
            )
        """)
        connection.execute("""
            INSERT OR IGNORE INTO assistant_identity
                (id, active_json, pending_json, active_version, pending_version, updated_at)
            VALUES (1, ?, NULL, 1, NULL, ?)
        """, (json.dumps(DEFAULT_IDENTITY, ensure_ascii=False), datetime.now(UTC).isoformat()))


def get_identity(*, database_path=None) -> dict[str, object]:
    """Return active and pending identity metadata without exposing raw SQL state."""
    path = database_path or get_database_path()
    _ensure_table(path)
    with _database(path) as connection:
        row = connection.execute(
            "SELECT active_json, pending_json, active_version, pending_version, updated_at "
            "FROM assistant_identity WHERE id = 1"
        ).fetchone()
    try:
        active = validate_identity(json.loads(row["active_json"]))
    except (ValueError, TypeError, json.JSONDecodeError):
        active = DEFAULT_IDENTITY.copy()
    try:
        pending = validate_identity(json.loads(row["pending_json"])) if row["pending_json"] else None
    except (ValueError, TypeError, json.JSONDecodeError):
        pending = None
    return {
        "active": active,
        "pending": pending,
        "active_version": int(row["active_version"]),
        "pending_version": int(row["pending_version"]) if pending is not None and row["pending_version"] is not None else None,
        "status": "pending_restart" if pending is not None else "active",
        "updated_at": str(row["updated_at"]),
    }


def get_active_identity(*, database_path=None) -> dict[str, object]:
    return get_identity(database_path=database_path)["active"]


def save_pending_identity(payload: dict[str, object], *, database_path=None) -> dict[str, object]:
    """Validate and save a pending profile without changing the currently active identity."""
    path = database_path or get_database_path()
    cleaned = validate_identity(payload)
    _ensure_table(path)
    now = datetime.now(UTC).isoformat()
    with _database(path) as connection:
        row = connection.execute(
            "SELECT active_version, pending_version FROM assistant_identity WHERE id = 1"
        ).fetchone()
        version = max(int(row["active_version"]), int(row["pending_version"] or 0)) + 1
        connection.execute(
            "UPDATE assistant_identity SET pending_json = ?, pending_version = ?, updated_at = ? WHERE id = 1",
            (json.dumps(cleaned, ensure_ascii=False), version, now),
        )
    return get_identity(database_path=path)


def activate_pending_identity(*, database_path=None) -> dict[str, object]:
    """Promote a previously validated pending profile during application startup."""
    path = database_path or get_database_path()
    _ensure_table(path)
    with _database(path) as connection:
        row = connection.execute(
            "SELECT pending_json, pending_version FROM assistant_identity WHERE id = 1"
        ).fetchone()
        if row["pending_json"] is not None:
            # Revalidate stored data before activation; malformed optional data never
            # prevents service startup and leaves the previous active profile intact.
            candidate = validate_identity(json.loads(row["pending_json"]))
            connection.execute(
                "UPDATE assistant_identity SET active_json = ?, active_version = ?, "
                "pending_json = NULL, pending_version = NULL, updated_at = ? WHERE id = 1",
                (json.dumps(candidate, ensure_ascii=False), int(row["pending_version"]), datetime.now(UTC).isoformat()),
            )
    return get_identity(database_path=path)
