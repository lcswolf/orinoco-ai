"""Per-user memory storage with strict owner scoping."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from orinoco.db import get_database_path


def _connect(path: Path | None = None) -> sqlite3.Connection:
    database = path or get_database_path()
    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection


def initialise_memory_store() -> None:
    with _connect() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                content TEXT NOT NULL CHECK(length(content) BETWEEN 1 AND 1000),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_memories_user_updated "
            "ON memories(user_id, updated_at DESC)"
        )


def list_memories(user_id: int) -> list[dict[str, object]]:
    initialise_memory_store()
    with _connect() as connection:
        rows = connection.execute(
            "SELECT id, content, created_at, updated_at FROM memories "
            "WHERE user_id = ? ORDER BY updated_at DESC, id DESC",
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def add_memory(user_id: int, content: str) -> dict[str, object]:
    cleaned = " ".join(content.split())
    if not cleaned or len(cleaned) > 1000:
        raise ValueError("Memory must contain 1–1000 characters.")
    initialise_memory_store()
    now = datetime.now(UTC).isoformat()
    with _connect() as connection:
        cursor = connection.execute(
            "INSERT INTO memories (user_id, content, created_at, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (user_id, cleaned, now, now),
        )
        memory_id = int(cursor.lastrowid)
    return {"id": memory_id, "content": cleaned, "created_at": now, "updated_at": now}


def update_memory(user_id: int, memory_id: int, content: str) -> bool:
    cleaned = " ".join(content.split())
    if not cleaned or len(cleaned) > 1000:
        raise ValueError("Memory must contain 1–1000 characters.")
    initialise_memory_store()
    now = datetime.now(UTC).isoformat()
    with _connect() as connection:
        cursor = connection.execute(
            "UPDATE memories SET content = ?, updated_at = ? "
            "WHERE id = ? AND user_id = ?",
            (cleaned, now, memory_id, user_id),
        )
        return cursor.rowcount == 1


def delete_memory(user_id: int, memory_id: int) -> bool:
    initialise_memory_store()
    with _connect() as connection:
        cursor = connection.execute(
            "DELETE FROM memories WHERE id = ? AND user_id = ?",
            (memory_id, user_id),
        )
        return cursor.rowcount == 1


def memory_context(user_id: int, limit: int = 12) -> list[str]:
    initialise_memory_store()
    with _connect() as connection:
        rows = connection.execute(
            "SELECT content FROM memories WHERE user_id = ? "
            "ORDER BY updated_at DESC, id DESC LIMIT ?",
            (user_id, max(1, min(limit, 20))),
        ).fetchall()
    return [str(row["content"]) for row in rows]
