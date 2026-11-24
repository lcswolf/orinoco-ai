"""Regression tests for the first-administrator bootstrap command."""

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

    assert main() == 0
    assert database.is_file()
    assert authenticate_user(
        "firstadmin",
        "a-very-long-admin-password-123",
        database_path=database,
    ) is not None
