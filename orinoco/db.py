"""Small SQLite persistence foundation for Orinoco accounts."""

from __future__ import annotations

import os
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from orinoco.auth.passwords import hash_password, verify_password

DEFAULT_DATABASE_PATH = Path(
    os.environ.get("ORINOCO_DATABASE_PATH", "/home/container/data/orinoco.sqlite3")
)


def get_database_path() -> Path:
    """Return the configured database path, resolving environment at call time."""
    return Path(os.environ.get("ORINOCO_DATABASE_PATH", str(DEFAULT_DATABASE_PATH)))


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


@contextmanager
def _database(database_path: Path) -> Iterator[sqlite3.Connection]:
    connection = _connect(database_path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialise_database(database_path: Path = DEFAULT_DATABASE_PATH) -> None:
    """Create the initial schema without overwriting existing user data."""
    with _database(database_path) as connection:
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
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_conversations_user_updated "
            "ON conversations(user_id, updated_at DESC)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_conversation "
            "ON messages(conversation_id, id)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                content TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('manual', 'automatic')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_memories_user_updated "
            "ON memories(user_id, updated_at DESC)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                scope TEXT NOT NULL CHECK (scope IN ('private', 'shared')),
                original_name TEXT NOT NULL,
                stored_path TEXT NOT NULL UNIQUE,
                file_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL CHECK (size_bytes > 0),
                sha256 TEXT NOT NULL,
                extracted_text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                CHECK (
                    (scope = 'private' AND owner_user_id IS NOT NULL)
                    OR (scope = 'shared' AND owner_user_id IS NULL)
                )
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_documents_owner "
            "ON documents(owner_user_id, created_at DESC)"
        )
        connection.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts "
            "USING fts5(original_name, extracted_text, tokenize='unicode61')"
        )
        connection.execute("PRAGMA user_version = 4")
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
        with _database(database_path) as connection:
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



def list_users(*, database_path: Path = DEFAULT_DATABASE_PATH) -> list[User]:
    with _database(database_path) as connection:
        rows = connection.execute(
            """
            SELECT id, username, role, active, created_at
            FROM users
            ORDER BY role DESC, username COLLATE NOCASE ASC
            """
        ).fetchall()
    return [
        User(
            id=int(row["id"]),
            username=str(row["username"]),
            role=str(row["role"]),
            active=bool(row["active"]),
            created_at=str(row["created_at"]),
        )
        for row in rows
    ]


def set_user_active(
    user_id: int,
    active: bool,
    *,
    database_path: Path = DEFAULT_DATABASE_PATH,
) -> bool:
    with _database(database_path) as connection:
        user = connection.execute(
            "SELECT role, active FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if user is None:
            return False
        if not active and str(user["role"]) == "admin" and bool(user["active"]):
            active_admins = connection.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'admin' AND active = 1"
            ).fetchone()[0]
            if int(active_admins) <= 1:
                raise AccountError("the last active administrator cannot be suspended")
        connection.execute(
            "UPDATE users SET active = ? WHERE id = ?",
            (1 if active else 0, user_id),
        )
        return True


def change_user_password(
    user_id: int,
    current_password: str,
    new_password: str,
    *,
    database_path: Path = DEFAULT_DATABASE_PATH,
) -> bool:
    try:
        new_hash = hash_password(new_password)
    except ValueError as exc:
        raise AccountError(str(exc)) from exc
    with _database(database_path) as connection:
        row = connection.execute(
            "SELECT password_hash, active FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if row is None or not bool(row["active"]):
            return False
        if not verify_password(current_password, str(row["password_hash"])):
            return False
        connection.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (new_hash, user_id),
        )
        return True


def get_user_by_username(
    username: str, *, database_path: Path = DEFAULT_DATABASE_PATH
) -> User | None:
    normalized = username.strip().lower()
    with _database(database_path) as connection:
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




def create_conversation(
    user_id: int,
    *,
    title: str = "New conversation",
    database_path: Path = DEFAULT_DATABASE_PATH,
) -> int:
    now = datetime.now(UTC).isoformat()
    safe_title = " ".join(title.split())[:80] or "New conversation"
    with _database(database_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO conversations (user_id, title, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, safe_title, now, now),
        )
        return int(cursor.lastrowid)


def list_conversations(
    user_id: int, *, database_path: Path = DEFAULT_DATABASE_PATH
) -> list[dict[str, object]]:
    with _database(database_path) as connection:
        rows = connection.execute(
            """
            SELECT c.id, c.title, c.created_at, c.updated_at,
                   (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS message_count
            FROM conversations c
            WHERE c.user_id = ?
            ORDER BY c.updated_at DESC, c.id DESC
            """,
            (user_id,),
        ).fetchall()
    return [
        {
            "id": int(row["id"]),
            "title": str(row["title"]),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
            "message_count": int(row["message_count"]),
        }
        for row in rows
    ]


def get_conversation(
    user_id: int,
    conversation_id: int,
    *,
    database_path: Path = DEFAULT_DATABASE_PATH,
) -> dict[str, object] | None:
    with _database(database_path) as connection:
        row = connection.execute(
            """
            SELECT id, title, created_at, updated_at
            FROM conversations WHERE id = ? AND user_id = ?
            """,
            (conversation_id, user_id),
        ).fetchone()
        if row is None:
            return None
        messages = connection.execute(
            """
            SELECT id, role, content, created_at
            FROM messages WHERE conversation_id = ?
            ORDER BY id ASC
            """,
            (conversation_id,),
        ).fetchall()
    return {
        "id": int(row["id"]),
        "title": str(row["title"]),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
        "messages": [
            {
                "id": int(message["id"]),
                "role": str(message["role"]),
                "content": str(message["content"]),
                "created_at": str(message["created_at"]),
            }
            for message in messages
        ],
    }



def save_exchange(
    user_id: int,
    conversation_id: int,
    user_content: str,
    assistant_content: str,
    *,
    database_path: Path = DEFAULT_DATABASE_PATH,
) -> bool:
    if not user_content.strip() or len(user_content) > 4000:
        raise ValueError("user message must contain 1–4000 characters")
    if not assistant_content.strip() or len(assistant_content) > 16000:
        raise ValueError("assistant response must contain 1–16000 characters")
    now = datetime.now(UTC).isoformat()
    with _database(database_path) as connection:
        owned = connection.execute(
            "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        ).fetchone()
        if owned is None:
            return False
        connection.executemany(
            """
            INSERT INTO messages (conversation_id, role, content, created_at)
            VALUES (?, ?, ?, ?)
            """,
            [
                (conversation_id, "user", user_content, now),
                (conversation_id, "assistant", assistant_content, now),
            ],
        )
        connection.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (now, conversation_id),
        )
        return True


def get_recent_messages(
    user_id: int,
    conversation_id: int,
    *,
    limit: int = 10,
    database_path: Path = DEFAULT_DATABASE_PATH,
) -> list[dict[str, str]]:
    bounded_limit = max(1, min(limit, 20))
    with _database(database_path) as connection:
        rows = connection.execute(
            """
            SELECT m.role, m.content
            FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            WHERE c.id = ? AND c.user_id = ?
            ORDER BY m.id DESC
            LIMIT ?
            """,
            (conversation_id, user_id, bounded_limit),
        ).fetchall()
    return [
        {"role": str(row["role"]), "content": str(row["content"])}
        for row in reversed(rows)
    ]


def add_conversation_message(
    user_id: int,
    conversation_id: int,
    role: str,
    content: str,
    *,
    database_path: Path = DEFAULT_DATABASE_PATH,
) -> int | None:
    if role not in {"user", "assistant"}:
        raise ValueError("role must be user or assistant")
    if not content.strip() or len(content) > 16000:
        raise ValueError("message must contain 1–16000 characters")
    now = datetime.now(UTC).isoformat()
    with _database(database_path) as connection:
        owned = connection.execute(
            "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        ).fetchone()
        if owned is None:
            return None
        cursor = connection.execute(
            """
            INSERT INTO messages (conversation_id, role, content, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (conversation_id, role, content, now),
        )
        connection.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (now, conversation_id),
        )
        return int(cursor.lastrowid)



def create_memory(
    user_id: int,
    content: str,
    *,
    source: str = "manual",
    database_path: Path = DEFAULT_DATABASE_PATH,
) -> int:
    """Save a memory owned by one user."""
    cleaned = " ".join(content.split())
    if not cleaned or len(cleaned) > 1000:
        raise ValueError("memory must contain 1–1000 characters")
    if source not in {"manual", "automatic"}:
        raise ValueError("memory source must be manual or automatic")
    now = datetime.now(UTC).isoformat()
    with _database(database_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO memories (user_id, content, source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, cleaned, source, now, now),
        )
        return int(cursor.lastrowid)


def list_memories(
    user_id: int,
    *,
    database_path: Path = DEFAULT_DATABASE_PATH,
) -> list[dict[str, object]]:
    """List only memories belonging to the requested account."""
    with _database(database_path) as connection:
        rows = connection.execute(
            """
            SELECT id, content, source, created_at, updated_at
            FROM memories
            WHERE user_id = ?
            ORDER BY updated_at DESC, id DESC
            """,
            (user_id,),
        ).fetchall()
    return [
        {
            "id": int(row["id"]),
            "content": str(row["content"]),
            "source": str(row["source"]),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
        }
        for row in rows
    ]


def update_memory(
    user_id: int,
    memory_id: int,
    content: str,
    *,
    database_path: Path = DEFAULT_DATABASE_PATH,
) -> bool:
    cleaned = " ".join(content.split())
    if not cleaned or len(cleaned) > 1000:
        raise ValueError("memory must contain 1–1000 characters")
    now = datetime.now(UTC).isoformat()
    with _database(database_path) as connection:
        cursor = connection.execute(
            "UPDATE memories SET content = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (cleaned, now, memory_id, user_id),
        )
        return cursor.rowcount == 1


def delete_memory(
    user_id: int,
    memory_id: int,
    *,
    database_path: Path = DEFAULT_DATABASE_PATH,
) -> bool:
    with _database(database_path) as connection:
        cursor = connection.execute(
            "DELETE FROM memories WHERE id = ? AND user_id = ?",
            (memory_id, user_id),
        )
        return cursor.rowcount == 1



def create_document(
    *,
    owner_user_id: int | None,
    scope: str,
    original_name: str,
    stored_path: str,
    file_type: str,
    size_bytes: int,
    sha256: str,
    extracted_text: str,
    database_path: Path = DEFAULT_DATABASE_PATH,
) -> int:
    if scope not in {"private", "shared"}:
        raise ValueError("document scope must be private or shared")
    if (scope == "private") != (owner_user_id is not None):
        raise ValueError("private documents require an owner; shared documents do not")
    if not extracted_text.strip() or len(extracted_text) > 200000:
        raise ValueError("extracted document text must contain 1–200000 characters")
    now = datetime.now(UTC).isoformat()
    with _database(database_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO documents (
                owner_user_id, scope, original_name, stored_path, file_type,
                size_bytes, sha256, extracted_text, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                owner_user_id, scope, original_name, stored_path, file_type,
                size_bytes, sha256, extracted_text, now,
            ),
        )
        document_id = int(cursor.lastrowid)
        connection.execute(
            "INSERT INTO documents_fts(rowid, original_name, extracted_text) VALUES (?, ?, ?)",
            (document_id, original_name, extracted_text),
        )
        return document_id


def list_documents(
    user_id: int,
    *,
    shared_only: bool = False,
    database_path: Path = DEFAULT_DATABASE_PATH,
) -> list[dict[str, object]]:
    with _database(database_path) as connection:
        if shared_only:
            rows = connection.execute(
                """
                SELECT id, scope, original_name, file_type, size_bytes, created_at
                FROM documents WHERE scope = 'shared'
                ORDER BY created_at DESC, id DESC
                """
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT id, scope, original_name, file_type, size_bytes, created_at
                FROM documents
                WHERE scope = 'shared' OR owner_user_id = ?
                ORDER BY created_at DESC, id DESC
                """,
                (user_id,),
            ).fetchall()
    return [
        {
            "id": int(row["id"]),
            "scope": str(row["scope"]),
            "original_name": str(row["original_name"]),
            "file_type": str(row["file_type"]),
            "size_bytes": int(row["size_bytes"]),
            "created_at": str(row["created_at"]),
        }
        for row in rows
    ]


def get_document(
    user_id: int,
    document_id: int,
    *,
    allow_shared: bool = True,
    database_path: Path = DEFAULT_DATABASE_PATH,
) -> dict[str, object] | None:
    with _database(database_path) as connection:
        row = connection.execute(
            """
            SELECT id, owner_user_id, scope, original_name, stored_path,
                   file_type, size_bytes, sha256, extracted_text, created_at
            FROM documents
            WHERE id = ? AND (owner_user_id = ? OR (scope = 'shared' AND ? = 1))
            """,
            (document_id, user_id, 1 if allow_shared else 0),
        ).fetchone()
    if row is None:
        return None
    return {
        "id": int(row["id"]),
        "owner_user_id": row["owner_user_id"],
        "scope": str(row["scope"]),
        "original_name": str(row["original_name"]),
        "stored_path": str(row["stored_path"]),
        "file_type": str(row["file_type"]),
        "size_bytes": int(row["size_bytes"]),
        "sha256": str(row["sha256"]),
        "extracted_text": str(row["extracted_text"]),
        "created_at": str(row["created_at"]),
    }


def delete_document(
    user_id: int,
    document_id: int,
    *,
    allow_shared: bool = False,
    database_path: Path = DEFAULT_DATABASE_PATH,
) -> str | None:
    with _database(database_path) as connection:
        row = connection.execute(
            """
            SELECT stored_path FROM documents
            WHERE id = ? AND (
                (scope = 'private' AND owner_user_id = ?)
                OR (scope = 'shared' AND ? = 1)
            )
            """,
            (document_id, user_id, 1 if allow_shared else 0),
        ).fetchone()
        if row is None:
            return None
        connection.execute("DELETE FROM documents_fts WHERE rowid = ?", (document_id,))
        connection.execute("DELETE FROM documents WHERE id = ?", (document_id,))
        return str(row["stored_path"])


def search_documents(
    user_id: int,
    query: str,
    *,
    limit: int = 3,
    database_path: Path = DEFAULT_DATABASE_PATH,
) -> list[dict[str, str]]:
    import re

    stop_words = {
        "what", "does", "my", "the", "and", "for", "about", "tell", "me",
        "this", "that", "please", "can", "you", "is", "are", "in", "on",
        "of", "to", "a", "an", "it", "i", "we", "our", "your",
    }
    terms = [
        term for term in re.findall(r"[A-Za-z0-9_]{2,}", query.lower())
        if term not in stop_words
    ][:8]
    if not terms:
        return []

    with _database(database_path) as connection:
        def run_search(match_query: str):
            return connection.execute(
                """
                SELECT d.id, d.original_name,
                       snippet(documents_fts, 1, '', '', ' … ', 18) AS excerpt
                FROM documents_fts
                JOIN documents d ON d.id = documents_fts.rowid
                WHERE documents_fts MATCH ?
                  AND (d.scope = 'shared' OR d.owner_user_id = ?)
                ORDER BY rank
                LIMIT ?
                """,
                (match_query, user_id, max(1, min(limit, 5))),
            ).fetchall()

        rows = run_search(" AND ".join(f'"{term}"' for term in terms))
        if not rows and len(terms) > 1:
            rows = run_search(" OR ".join(f'"{term}"' for term in terms))

    return [
        {
            "id": str(row["id"]),
            "name": str(row["original_name"]),
            "excerpt": str(row["excerpt"])[:1600],
        }
        for row in rows
    ]

def get_user_by_id(
    user_id: int, *, database_path: Path = DEFAULT_DATABASE_PATH
) -> User | None:
    with _database(database_path) as connection:
        row = connection.execute(
            """
            SELECT id, username, role, active, created_at
            FROM users WHERE id = ?
            """,
            (user_id,),
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
    with _database(database_path) as connection:
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
