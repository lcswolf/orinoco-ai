"""Regression tests for the first-administrator bootstrap command."""

from types import SimpleNamespace

from orinoco.admin.cli import main
from orinoco.db import authenticate_user


def test_admin_bootstrap_uses_configured_database_path(tmp_path, monkeypatch) -> None:
    """The documented module command must create the first admin in the selected database."""
    database = tmp_path / "custom" / "orinoco.sqlite3"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    monkeypatch.setattr("builtins.input", lambda prompt: "firstadmin")

    passwords = iter(["a-very-long-admin-password-123", "a-very-long-admin-password-123"])
    monkeypatch.setattr("orinoco.admin.cli.getpass.getpass", lambda prompt: next(passwords))
    monkeypatch.setattr("sys.argv", ["python -m orinoco.admin", "create-admin"])
    monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: True))

    assert main() == 0
    assert database.is_file()
    assert authenticate_user(
        "firstadmin",
        "a-very-long-admin-password-123",
        database_path=database,
    ) is not None


def test_admin_bootstrap_refuses_when_any_account_already_exists(tmp_path, monkeypatch) -> None:
    """The one-time setup command must not become an alternate admin-creation path."""
    from orinoco.db import create_user, initialise_database

    database = tmp_path / "existing.sqlite3"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    initialise_database(database)
    create_user("existinguser", "a-long-existing-password-123", database_path=database)
    monkeypatch.setattr("builtins.input", lambda prompt: (_ for _ in ()).throw(AssertionError("must not prompt")))
    monkeypatch.setattr("sys.argv", ["python -m orinoco.admin", "create-admin"])

    assert main() == 2


def test_admin_package_exposes_documented_module_command() -> None:
    """The package entry point must make the documented -m commands executable."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "orinoco.admin", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "create-admin" in result.stdout
    assert "reset-password" in result.stdout


def test_admin_password_reset_uses_configured_database_and_revokes_sessions(
    tmp_path, monkeypatch
) -> None:
    """The offline recovery command resets a password in the selected database."""
    from orinoco.db import create_user, get_user_by_username, initialise_database

    database = tmp_path / "custom" / "orinoco.sqlite3"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    initialise_database(database)
    user = create_user("recoveradmin", "an-old-long-password-123", role="admin", database_path=database)
    old_version = user.session_version
    monkeypatch.setattr("builtins.input", lambda prompt: "recoveradmin")
    passwords = iter(["a-new-long-password-456", "a-new-long-password-456"])
    monkeypatch.setattr("orinoco.admin.cli.getpass.getpass", lambda prompt: next(passwords))
    monkeypatch.setattr("sys.argv", ["python -m orinoco.admin", "reset-password", "recoveradmin"])
    monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: True))

    assert main() == 0
    assert authenticate_user(
        "recoveradmin",
        "an-old-long-password-123",
        database_path=database,
    ) is None
    assert authenticate_user(
        "recoveradmin",
        "a-new-long-password-456",
        database_path=database,
    ) is not None
    updated = get_user_by_username("recoveradmin", database_path=database)
    assert updated is not None
    assert updated.session_version == old_version + 1


def test_admin_password_reset_requires_exact_account_confirmation(tmp_path, monkeypatch) -> None:
    """A mistyped account confirmation must not change any credentials."""
    import pytest
    from orinoco.db import create_user, initialise_database

    database = tmp_path / "accounts.sqlite3"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    initialise_database(database)
    create_user("recoveradmin", "an-old-long-password-123", role="admin", database_path=database)
    monkeypatch.setattr("builtins.input", lambda prompt: "different-account")
    monkeypatch.setattr(
        "orinoco.admin.cli.getpass.getpass",
        lambda prompt: pytest.fail("password prompt must not be reached"),
    )
    monkeypatch.setattr("sys.argv", ["python -m orinoco.admin", "reset-password", "recoveradmin"])
    monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: True))

    assert main() == 2


def test_admin_password_reset_refuses_noninteractive_password_input(tmp_path, monkeypatch) -> None:
    """Do not fall back to echoed stdin when the command has no terminal."""
    from orinoco.db import create_user, initialise_database

    database = tmp_path / "accounts.sqlite3"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    initialise_database(database)
    create_user("recoveradmin", "an-old-long-password-123", role="admin", database_path=database)
    monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: False))
    monkeypatch.setattr("builtins.input", lambda prompt: (_ for _ in ()).throw(AssertionError("must not prompt")))
    monkeypatch.setattr(
        "orinoco.admin.cli.getpass.getpass",
        lambda prompt: (_ for _ in ()).throw(AssertionError("password must not be read")),
    )
    monkeypatch.setattr("sys.argv", ["python -m orinoco.admin", "reset-password", "recoveradmin"])

    assert main() == 2


def test_initial_admin_bootstrap_refuses_noninteractive_password_input(tmp_path, monkeypatch) -> None:
    """The first-admin command must not echo the bootstrap password into process logs."""
    from orinoco.db import initialise_database, list_users

    database = tmp_path / "accounts.sqlite3"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    initialise_database(database)
    monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: False))
    monkeypatch.setattr("builtins.input", lambda prompt: (_ for _ in ()).throw(AssertionError("must not prompt")))
    monkeypatch.setattr(
        "orinoco.admin.cli.getpass.getpass",
        lambda prompt: (_ for _ in ()).throw(AssertionError("password must not be read")),
    )
    monkeypatch.setattr("sys.argv", ["python -m orinoco.admin", "create-admin"])

    assert main() == 2
    assert list_users(database_path=database) == []


def test_create_first_admin_is_one_time_and_refuses_existing_accounts(tmp_path) -> None:
    """The browser bootstrap persistence operation can only create one first account."""
    import pytest
    from orinoco.db import AccountError, create_first_admin, list_users

    database = tmp_path / "first-admin.sqlite3"
    first = create_first_admin(
        "firstadmin",
        "a-long-first-admin-password-123",
        database_path=database,
    )
    assert first.role == "admin"
    assert [user.username for user in list_users(database_path=database)] == ["firstadmin"]

    with pytest.raises(AccountError, match="setup has already been completed"):
        create_first_admin(
            "secondadmin",
            "a-long-second-admin-password-123",
            database_path=database,
        )
    assert [user.username for user in list_users(database_path=database)] == ["firstadmin"]


def test_create_first_admin_rejects_invalid_password_without_creating_account(tmp_path) -> None:
    """Invalid bootstrap credentials leave the database ready for a valid setup attempt."""
    import pytest
    from orinoco.db import AccountError, create_first_admin, list_users

    database = tmp_path / "invalid-first-admin.sqlite3"
    with pytest.raises(AccountError):
        create_first_admin("firstadmin", "short", database_path=database)
    assert list_users(database_path=database) == []


def test_admin_recovery_token_resets_password_once_and_revokes_sessions(tmp_path) -> None:
    """Recovery tokens are consumed durably and each reset invalidates old sessions."""
    from orinoco.db import (
        create_user,
        initialise_database,
        reset_admin_password_with_recovery_token,
    )

    database = tmp_path / "admin-recovery.sqlite3"
    initialise_database(database)
    admin = create_user(
        "recoveradmin",
        "an-old-admin-password-123",
        role="admin",
        database_path=database,
    )
    first = reset_admin_password_with_recovery_token(
        "recoveradmin",
        "a-new-admin-password-456",
        "panel-recovery-token-with-at-least-32-random-characters",
        database_path=database,
    )
    assert first is not None
    assert first.session_version == admin.session_version + 1

    assert reset_admin_password_with_recovery_token(
        "recoveradmin",
        "a-third-admin-password-789",
        "panel-recovery-token-with-at-least-32-random-characters",
        database_path=database,
    ) is None

    # A different, newly armed token can be used for a later recovery.
    second = reset_admin_password_with_recovery_token(
        "recoveradmin",
        "a-third-admin-password-789",
        "a-different-panel-recovery-token-with-at-least-32-random-characters",
        database_path=database,
    )
    assert second is not None
    assert second.session_version == admin.session_version + 2


def test_admin_recovery_refuses_unknown_or_inactive_accounts(tmp_path) -> None:
    """A recovery token cannot be used to create an account or reactivate one."""
    from orinoco.db import create_user, initialise_database, reset_admin_password_with_recovery_token, set_user_active

    database = tmp_path / "admin-recovery-inactive.sqlite3"
    initialise_database(database)
    admin = create_user("recoveradmin", "an-old-admin-password-123", role="admin", database_path=database)
    assert set_user_active(admin.id, False, database_path=database) is True

    assert reset_admin_password_with_recovery_token(
        "recoveradmin",
        "a-new-admin-password-456",
        "panel-recovery-token-with-at-least-32-random-characters",
        database_path=database,
    ) is None
    assert reset_admin_password_with_recovery_token(
        "missingadmin",
        "a-new-admin-password-456",
        "a-different-panel-recovery-token-with-at-least-32-random-characters",
        database_path=database,
    ) is None
