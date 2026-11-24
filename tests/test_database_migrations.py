"""Tests for additive SQLite schema upgrades and forward-version protection."""

import sqlite3

import pytest

from orinoco.db import CURRENT_SCHEMA_VERSION, authenticate_user, create_user, initialise_database


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
        user_columns = {row[1] for row in connection.execute("PRAGMA table_info(users)")}
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
            )
        }

    assert version == CURRENT_SCHEMA_VERSION
    assert "session_version" in user_columns
    assert {"users", "conversations", "messages", "memories", "documents", "documents_fts", "user_preferences", "assistant_persona"} <= tables


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


def test_database_file_permissions_are_restricted(tmp_path) -> None:
    """SQLite persistence files should be owner-readable only on POSIX systems."""
    import os

    database = tmp_path / "private.sqlite3"
    initialise_database(database)

    if os.name == "posix":
        assert database.stat().st_mode & 0o777 == 0o600


def test_database_refuses_symbolic_link_path(tmp_path) -> None:
    """A database path must not redirect private persistence into another location."""
    target = tmp_path / "external.sqlite3"
    with sqlite3.connect(target) as connection:
        connection.execute("CREATE TABLE external_data (value TEXT)")
    link = tmp_path / "orinoco.sqlite3"
    link.symlink_to(target)

    with pytest.raises(RuntimeError, match="database path must not be a symbolic link"):
        initialise_database(link)

    with sqlite3.connect(target) as connection:
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchone()[0] == "external_data"


def test_database_parent_directory_permissions_are_restricted(tmp_path) -> None:
    """The directory holding the database and private user data is owner-only on POSIX."""
    import os

    database_dir = tmp_path / "private-data"
    database = database_dir / "orinoco.sqlite3"
    initialise_database(database)

    if os.name == "posix":
        assert database_dir.stat().st_mode & 0o777 == 0o700


def test_v5_database_upgrades_to_current_schema_without_losing_accounts(tmp_path) -> None:
    """The preference/persona migrations preserve account data from schema v5."""
    from orinoco.db import CURRENT_SCHEMA_VERSION, get_assistant_persona, get_user_preferences

    database = tmp_path / "v5-upgrade.sqlite3"
    initialise_database(database)
    user = create_user("schemafive", "a-long-test-password-123", database_path=database)
    with sqlite3.connect(database) as connection:
        connection.execute("DROP TABLE user_preferences")
        connection.execute("DROP TABLE assistant_persona")
        connection.execute("PRAGMA user_version = 5")

    initialise_database(database)

    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == CURRENT_SCHEMA_VERSION
    assert authenticate_user(
        "schemafive", "a-long-test-password-123", database_path=database
    ) is not None
    assert get_user_preferences(user.id, database_path=database)["voice"] == "bright"
    assert get_assistant_persona(database_path=database)["humour_level"] == 65
