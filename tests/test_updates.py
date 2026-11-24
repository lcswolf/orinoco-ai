"""Tests for backup-gated application update preparation and migrations."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from orinoco import updates
from orinoco.db import CURRENT_SCHEMA_VERSION, initialise_database


def test_prepare_update_creates_verifies_and_uploads_when_configured(tmp_path, monkeypatch) -> None:
    """The pre-update command must verify its backup and include a configured remote upload."""
    backup = tmp_path / "orinoco-before-update.oribak"
    backup.write_bytes(b"encrypted")
    monkeypatch.setenv("ORINOCO_BACKUP_S3_ENDPOINT", "https://objects.example.test")
    monkeypatch.setattr(updates, "create_backup", lambda: backup)
    monkeypatch.setattr(updates, "verify_backup", lambda path: {"format": "orinoco-backup-v1"})
    monkeypatch.setattr(
        updates,
        "upload_backup",
        lambda path: {"bucket": "private", "key": path.name, "verified": True},
    )

    result = updates.prepare_update()

    assert result["backup"] == str(backup)
    assert result["verified"] is True
    assert result["upload"]["verified"] is True


def test_migration_requires_a_verified_backup_for_existing_database(tmp_path, monkeypatch) -> None:
    """Never upgrade an existing database unless a pre-migration backup was supplied."""
    database = tmp_path / "orinoco.sqlite3"
    initialise_database(database)
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))

    with pytest.raises(updates.UpdateError, match="requires --backup"):
        updates.migrate_database()


def test_migration_verifies_backup_before_initialising_database(tmp_path, monkeypatch) -> None:
    """The migration step checks the supplied backup before changing schema state."""
    database = tmp_path / "orinoco.sqlite3"
    initialise_database(database)
    backup = tmp_path / "before.oribak"
    backup.write_bytes(b"placeholder encrypted archive")
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    verified: list[Path] = []
    monkeypatch.setattr(updates, "verify_backup", lambda path: verified.append(path) or {"verified": True})

    result = updates.migrate_database(backup_path=backup)

    assert verified == [backup]
    assert result["schema_version"] == CURRENT_SCHEMA_VERSION
    assert result["integrity"] == "ok"
    assert result["backup_verified"] is True


def test_migration_does_not_touch_database_when_backup_verification_fails(tmp_path, monkeypatch) -> None:
    """An invalid backup prevents migration from starting."""
    database = tmp_path / "orinoco.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA user_version = 0")
    backup = tmp_path / "bad.oribak"
    backup.write_bytes(b"not a valid backup")
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))

    def reject_backup(path):
        raise updates.BackupError("backup authentication failed")

    monkeypatch.setattr(updates, "verify_backup", reject_backup)
    with pytest.raises(updates.UpdateError, match="could not be verified"):
        updates.migrate_database(backup_path=backup)

    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 0


def test_fresh_install_migration_does_not_require_backup(tmp_path, monkeypatch) -> None:
    """A new installation can initialise its first schema without a prior backup."""
    database = tmp_path / "fresh.sqlite3"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))

    result = updates.migrate_database()

    assert result["schema_version"] == CURRENT_SCHEMA_VERSION
    assert result["backup_verified"] is True
    assert database.is_file()


def test_update_cli_emits_json_and_returns_success(monkeypatch, capsys) -> None:
    """The one-shot prepare command has machine-readable success output."""
    monkeypatch.setattr(
        updates,
        "prepare_update",
        lambda: {"backup": "/data/backup.oribak", "verified": True, "upload": None},
    )

    assert updates.main(["prepare"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["verified"] is True


def test_migration_rejects_foreign_key_inconsistency_after_schema_changes(tmp_path, monkeypatch) -> None:
    """The migration command must not report success with orphaned application rows."""
    database = tmp_path / "orinoco.sqlite3"
    initialise_database(database)
    backup = tmp_path / "before.oribak"
    backup.write_bytes(b"placeholder encrypted archive")
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    monkeypatch.setattr(updates, "verify_backup", lambda path: {"verified": True})
    real_initialise = updates.initialise_database

    def initialise_with_orphan(database_path: Path) -> None:
        real_initialise(database_path)
        # Simulate a migration defect that bypasses SQLite's per-connection FK
        # enforcement. The post-migration integrity check must still catch it.
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                """
                INSERT INTO conversations (user_id, title, created_at, updated_at)
                VALUES (999999, 'orphaned', '2026-11-24T00:00:00+00:00', '2026-11-24T00:00:00+00:00')
                """
            )

    monkeypatch.setattr(updates, "initialise_database", initialise_with_orphan)

    with pytest.raises(updates.UpdateError, match="foreign-key consistency errors"):
        updates.migrate_database(backup_path=backup)
