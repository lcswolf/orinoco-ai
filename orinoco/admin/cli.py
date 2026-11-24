"""Interactive, local-only administration commands."""

from __future__ import annotations

import argparse
import getpass
import sys

from pathlib import Path

from orinoco.db import (
    AccountError,
    create_user,
    get_database_path,
    get_user_by_username,
    initialise_database,
    list_users,
    reset_user_password,
)


def _require_interactive_terminal() -> bool:
    """Refuse password prompts without a TTY so getpass cannot echo secrets."""
    if sys.stdin.isatty():
        return True
    print(
        "This command requires an interactive terminal so passwords are not echoed. "
        "Run it through an SSH session with a TTY.",
        file=sys.stderr,
    )
    return False


def create_initial_admin(database_path: Path | None = None) -> int:
    """Create the first administrator only when no account exists; never reset an existing installation."""
    database_path = database_path or get_database_path()
    initialise_database(database_path)
    if list_users(database_path=database_path):
        print("Orinoco already has an account; refusing to create another bootstrap administrator.", file=sys.stderr)
        return 2
    if not _require_interactive_terminal():
        return 2
    print("Create the first Orinoco administrator account.")
    print("Usernames: 3–32 characters; letters, numbers, dots, underscores or hyphens.")
    username = input("Administrator username: ").strip()
    password = getpass.getpass("Password (at least 12 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        print("The passwords did not match.", file=sys.stderr)
        return 2
    try:
        user = create_user(username, password, role="admin", database_path=database_path)
    except AccountError as exc:
        print(f"Could not create administrator: {exc}", file=sys.stderr)
        return 2
    print(f"Administrator account '{user.username}' created.")
    print("Keep your password safe. Public registration is not enabled.")
    return 0


def reset_account_password(username: str, database_path: Path | None = None) -> int:
    """Reset one account password locally after an explicit username confirmation."""
    database_path = database_path or get_database_path()
    initialise_database(database_path)
    user = get_user_by_username(username, database_path=database_path)
    if user is None:
        print("No account with that username exists.", file=sys.stderr)
        return 2
    if not _require_interactive_terminal():
        return 2

    print(f"Reset the password for '{user.username}' ({user.role}).")
    confirmation_name = input(f"Type {user.username} to confirm: ").strip()
    if confirmation_name != user.username:
        print("The account name did not match; no password was changed.", file=sys.stderr)
        return 2

    password = getpass.getpass("New password (at least 12 characters): ")
    confirmation = getpass.getpass("Confirm new password: ")
    if password != confirmation:
        print("The passwords did not match; no password was changed.", file=sys.stderr)
        return 2

    try:
        changed = reset_user_password(user.id, password, database_path=database_path)
    except AccountError as exc:
        print(f"Could not reset password: {exc}", file=sys.stderr)
        return 2
    if not changed:
        print("The account no longer exists; no password was changed.", file=sys.stderr)
        return 2

    print(f"Password reset for '{user.username}'. All existing sessions have been revoked.")
    return 0


def main() -> int:
    """Parse the command-line options for the one-time initial administrator setup."""
    parser = argparse.ArgumentParser(prog="python -m orinoco.admin")
    parser.add_argument("command", choices=("create-admin", "reset-password"))
    parser.add_argument("username", nargs="?", help="account username for reset-password")
    args = parser.parse_args()
    if args.command == "create-admin":
        if args.username:
            parser.error("create-admin does not accept a username")
        return create_initial_admin()
    if args.command == "reset-password":
        if not args.username:
            parser.error("reset-password requires an account username")
        return reset_account_password(args.username)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
