"""Pre-update backup and explicit SQLite migration commands for Orinoco.

These commands are intended to run as one-shot Pterodactyl startup commands
while the normal Supervisor-managed application is stopped. They do not
download or switch container images; Pterodactyl remains the update manager.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tarfile
from pathlib import Path

from orinoco.backups import BackupError, create_backup, restore_backup, upload_backup, verify_backup
from orinoco.db import CURRENT_SCHEMA_VERSION, get_database_path, initialise_database


class UpdateError(RuntimeError):
    """Raised when a safe pre-update or migration check cannot be completed."""


def prepare_update() -> dict[str, object]:
    """Create and verify a fresh encrypted backup, uploading it when S3 is configured."""
    backup_path = create_backup()
    manifest = verify_backup(backup_path)
    upload_result: dict[str, object] | None = None
    if os.environ.get("ORINOCO_BACKUP_S3_ENDPOINT", "").strip():
        upload_result = upload_backup(backup_path)
    return {
        "backup": str(backup_path),
        "verified": True,
        "manifest": manifest,
        "upload": upload_result,
    }


def migrate_database(*, backup_path: Path | None = None) -> dict[str, object]:
    """Apply the known additive schema migrations after verifying a pre-migration backup."""
    database_path = get_database_path()
    database_exists = database_path.exists()

    if database_path.is_symlink():
        raise UpdateError("The configured database path must not be a symbolic link.")

    if database_exists:
        if backup_path is None:
            raise UpdateError(
                "An existing database requires --backup with a verified pre-migration .oribak file."
            )
        try:
            verify_backup(backup_path)
        except (BackupError, OSError, sqlite3.Error) as exc:
            raise UpdateError(f"The pre-migration backup could not be verified: {exc}") from exc

    try:
        initialise_database(database_path)

        connection = sqlite3.connect(database_path)
        try:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            schema_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            foreign_key_issue = connection.execute("PRAGMA foreign_key_check").fetchone()
        finally:
            connection.close()

        if not integrity or integrity[0] != "ok":
            raise UpdateError("The database failed its post-migration integrity check.")
        if foreign_key_issue:
            raise UpdateError("The database contains foreign-key consistency errors after migration.")
        if schema_version != CURRENT_SCHEMA_VERSION:
            raise UpdateError(
                f"Expected schema version {CURRENT_SCHEMA_VERSION}, found {schema_version}."
            )
    except Exception as migration_error:
        # A verified encrypted backup is mandatory for an existing database.
        # If migration or its integrity checks fail, restore that snapshot
        # immediately while the app is stopped rather than leaving a partial
        # schema upgrade for the operator to diagnose.
        if database_exists and backup_path is not None:
            try:
                restore_backup(backup_path, confirm=True)
            except Exception as restore_error:
                raise UpdateError(
                    f"Migration failed ({migration_error}); automatic restore also failed "
                    f"({restore_error}). Stop Orinoco and perform the manual restore "
                    f"from the verified backup."
                ) from migration_error
            raise UpdateError(
                f"Migration failed and the verified pre-migration backup was automatically "
                f"restored: {migration_error}"
            ) from migration_error
        raise
    return {
        "database": str(database_path),
        "schema_version": schema_version,
        "integrity": "ok",
        "backup_verified": backup_path is not None or not database_exists,
    }


def main(argv: list[str] | None = None) -> int:
    """Run the one-shot update preparation or migration command."""
    parser = argparse.ArgumentParser(description="Orinoco safe update preparation and migration")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("prepare", help="create, verify and optionally upload a pre-update backup")
    migrate = commands.add_parser("migrate", help="apply additive SQLite migrations after backup verification")
    migrate.add_argument("--backup", type=Path, help="verified pre-migration encrypted backup")
    args = parser.parse_args(argv)

    try:
        if args.command == "prepare":
            result = prepare_update()
        else:
            result = migrate_database(backup_path=args.backup)
        print(json.dumps(result, indent=2))
        return 0
    except (RuntimeError, OSError, sqlite3.Error, ValueError, tarfile.TarError) as exc:
        print(f"Orinoco update error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
