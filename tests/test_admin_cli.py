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
