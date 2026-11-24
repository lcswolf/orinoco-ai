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
    return _list_memories(user_id, database_path=get_database_path())


def add_memory(user_id: int, content: str) -> dict[str, object]:
    memory_id = create_memory(user_id, content, database_path=get_database_path())
    return next(item for item in list_memories(user_id) if item["id"] == memory_id)


def update_memory(user_id: int, memory_id: int, content: str) -> bool:
    return _update_memory(
        user_id, memory_id, content, database_path=get_database_path()
    )


def delete_memory(user_id: int, memory_id: int) -> bool:
    return _delete_memory(user_id, memory_id, database_path=get_database_path())


def memory_context(user_id: int, limit: int = 12) -> list[str]:
    return [
        str(item["content"])
        for item in list_memories(user_id)[: max(1, min(limit, 20))]
    ]
