"""Tests for additive SQLite schema upgrades and forward-version protection."""

import sqlite3

import pytest

from orinoco.db import CURRENT_SCHEMA_VERSION, initialise_database


def test_legacy_v1_database_is_upgraded_additively(tmp_path) -> None:
    """An early users-only database receives the later additive feature tables."""
    database = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('admin', 'user')),
                active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute("PRAGMA user_version = 1")

    initialise_database(database)

    with sqlite3.connect(database) as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
            )
        }

    assert version == CURRENT_SCHEMA_VERSION
    assert {"users", "conversations", "messages", "memories", "documents", "documents_fts"} <= tables


def test_newer_database_schema_is_never_downgraded_or_modified(tmp_path) -> None:
    """An older app build must refuse a database created by a newer schema."""
    database = tmp_path / "future.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA user_version = 99")

    with pytest.raises(RuntimeError, match="newer than this Orinoco build"):
        initialise_database(database)

    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 99
        tables = connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()[0]

    assert tables == 0
