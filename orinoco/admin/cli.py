"""Interactive, local-only administration commands."""

from __future__ import annotations

import argparse
import getpass
import sys

from pathlib import Path

from orinoco.db import AccountError, create_user, get_database_path, initialise_database


def create_initial_admin(database_path: Path | None = None) -> int:
    """Create the first administrator only when no account exists; never reset an existing installation."""
    database_path = database_path or get_database_path()
    initialise_database(database_path)
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


def main() -> int:
    """Parse the command-line options for the one-time initial administrator setup."""
    parser = argparse.ArgumentParser(prog="python -m orinoco.admin")
    parser.add_argument("command", choices=("create-admin",))
    args = parser.parse_args()
    if args.command == "create-admin":
        return create_initial_admin()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
