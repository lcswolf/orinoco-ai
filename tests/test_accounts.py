"""Tests for Orinoco's local account database and password handling."""

import sqlite3

import pytest

from orinoco.db import (
    AccountError,
    authenticate_user,
    create_user,
    get_user_by_username,
    initialise_database,
)


def test_create_and_authenticate_user(tmp_path) -> None:
    database = tmp_path / "orinoco.sqlite3"
    initialise_database(database)
    created = create_user(
        "Nugget.User",
        "a-long-test-password-123",
        role="admin",
        database_path=database,
    )

    assert created.username == "nugget.user"
    assert created.role == "admin"
    assert authenticate_user(
        "NUGGET.USER", "a-long-test-password-123", database_path=database
    ) == created
    assert authenticate_user("nugget.user", "wrong-password", database_path=database) is None


def test_passwords_must_be_at_least_twelve_characters(tmp_path) -> None:
    database = tmp_path / "orinoco.sqlite3"
    initialise_database(database)

    with pytest.raises(AccountError, match="12 characters"):
        create_user("nugget", "short", database_path=database)


def test_usernames_are_validated_and_unique(tmp_path) -> None:
    database = tmp_path / "orinoco.sqlite3"
    initialise_database(database)
    create_user("nugget", "a-long-test-password-123", database_path=database)

    with pytest.raises(AccountError, match="already in use"):
        create_user("NUGGET", "another-long-test-password", database_path=database)

    with pytest.raises(AccountError, match="username"):
        create_user("not valid!", "another-long-test-password", database_path=database)


def test_inactive_users_cannot_authenticate(tmp_path) -> None:
    database = tmp_path / "orinoco.sqlite3"
    initialise_database(database)
    user = create_user("nugget", "a-long-test-password-123", database_path=database)

    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE users SET active = 0 WHERE id = ?", (user.id,))

    assert authenticate_user("nugget", "a-long-test-password-123", database_path=database) is None
    assert get_user_by_username("nugget", database_path=database).active is False
