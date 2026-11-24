"""Small SQLite persistence foundation for Orinoco accounts."""

from __future__ import annotations

import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from orinoco.auth.passwords import hash_password, verify_password

DEFAULT_DATABASE_PATH = Path(
    os.environ.get("ORINOCO_DATABASE_PATH", "/home/container/data/orinoco.sqlite3")
)
_USERNAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.-]{2,31}$")


@dataclass(frozen=True)
class User:
    id: int
    username: str
    role: str
    active: bool
    created_at: str


class AccountError(ValueError):
    """Raised when an account cannot be created or authenticated."""


def _connect(database_path: Path) -> sqlite3.Connection:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection


def initialise_database(database_path: Path = DEFAULT_DATABASE_PATH) -> None:
    """Create the initial schema without overwriting existing user data."""
    with _connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('admin', 'user')),
                active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")
        connection.execute("PRAGMA user_version = 1")
    try:
        database_path.chmod(0o600)
    except OSError:
        # The container directory is private; some mounted filesystems do not
        # support chmod. Deployment checks will verify permissions separately.
        pass


def _validate_username(username: str) -> str:
    normalized = username.strip().lower()
    if not _USERNAME_PATTERN.fullmatch(normalized):
        raise AccountError(
            "username must be 3–32 characters using letters, numbers, dots, "
            "underscores or hyphens"
        )
    return normalized


def create_user(
    username: str,
    password: str,
    *,
    role: str = "user",
    database_path: Path = DEFAULT_DATABASE_PATH,
) -> User:
    if role not in {"admin", "user"}:
        raise AccountError("role must be admin or user")
    normalized = _validate_username(username)
    try:
        password_hash = hash_password(password)
    except ValueError as exc:
        raise AccountError(str(exc)) from exc

    created_at = datetime.now(UTC).isoformat()
    try:
        with _connect(database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO users (username, password_hash, role, active, created_at)
                VALUES (?, ?, ?, 1, ?)
                """,
                (normalized, password_hash, role, created_at),
            )
            user_id = int(cursor.lastrowid)
    except sqlite3.IntegrityError as exc:
        raise AccountError("that username is already in use") from exc

    try:
        database_path.chmod(0o600)
    except OSError:
        pass

    return User(
        id=user_id,
        username=normalized,
        role=role,
        active=True,
        created_at=created_at,
    )


def get_user_by_username(
    username: str, *, database_path: Path = DEFAULT_DATABASE_PATH
) -> User | None:
    normalized = username.strip().lower()
    with _connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT id, username, role, active, created_at
            FROM users WHERE username = ? COLLATE NOCASE
            """,
            (normalized,),
        ).fetchone()
    if row is None:
        return None
    return User(
        id=int(row["id"]),
        username=str(row["username"]),
        role=str(row["role"]),
        active=bool(row["active"]),
        created_at=str(row["created_at"]),
    )


def authenticate_user(
    username: str,
    password: str,
    *,
    database_path: Path = DEFAULT_DATABASE_PATH,
) -> User | None:
    normalized = username.strip().lower()
    with _connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT id, username, password_hash, role, active, created_at
            FROM users WHERE username = ? COLLATE NOCASE
            """,
            (normalized,),
        ).fetchone()
    if row is None or not bool(row["active"]):
        return None
    if not verify_password(password, str(row["password_hash"])):
        return None
    return User(
        id=int(row["id"]),
        username=str(row["username"]),
        role=str(row["role"]),
        active=True,
        created_at=str(row["created_at"]),
    )
