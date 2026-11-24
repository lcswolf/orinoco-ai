"""Compatibility helpers for the shared per-user memory database."""

from __future__ import annotations

from orinoco.db import (
    create_memory,
    delete_memory as _delete_memory,
    get_database_path,
    list_memories as _list_memories,
    update_memory as _update_memory,
)


def list_memories(user_id: int) -> list[dict[str, object]]:
    """Return the account's memories through the shared database layer."""
    return _list_memories(user_id, database_path=get_database_path())


def add_memory(user_id: int, content: str) -> dict[str, object]:
    """Create a manual memory for the supplied account."""
    memory_id = create_memory(user_id, content, database_path=get_database_path())
    return next(item for item in list_memories(user_id) if item["id"] == memory_id)


def update_memory(user_id: int, memory_id: int, content: str) -> bool:
    """Update a memory only when it belongs to the supplied account."""
    return _update_memory(
        user_id, memory_id, content, database_path=get_database_path()
    )


def delete_memory(user_id: int, memory_id: int) -> bool:
    """Delete a memory only when it belongs to the supplied account."""
    return _delete_memory(user_id, memory_id, database_path=get_database_path())


def memory_context(user_id: int, limit: int = 12) -> list[str]:
    """Build a bounded list of this account's memory facts for chat context."""
    return [
        str(item["content"])
        for item in list_memories(user_id)[: max(1, min(limit, 20))]
    ]
