"""Tests for encrypted Orinoco backup creation, verification and recovery."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from orinoco import backups
from orinoco.db import create_user, initialise_database


def configure_backup_paths(monkeypatch, tmp_path: Path) -> tuple[Path, Path, Path]:
    """Point every persistent data location at an isolated temporary directory."""
    data = tmp_path / "data"
    database = data / "orinoco.sqlite3"
    documents = data / "documents"
    backup_root = tmp_path / "backups"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    monkeypatch.setenv("ORINOCO_DOCUMENTS_PATH", str(documents))
    monkeypatch.setenv("ORINOCO_SESSION_SECRET_PATH", str(data / ".session_secret"))
    monkeypatch.setenv("ORINOCO_BACKUP_PATH", str(backup_root))
    monkeypatch.setenv("ORINOCO_BACKUP_KEY", backups.generate_key())
    initialise_database(database)
    create_user("backup-user", "a-long-test-password-123", database_path=database)
    documents.mkdir(parents=True)
    (documents / "private").mkdir()
    (documents / "private" / "note.txt").write_text("private backup content", encoding="utf-8")
    (data / ".session_secret").write_text("test-session-secret-value-which-is-long-enough", encoding="utf-8")
    return database, documents, backup_root


def test_backup_is_encrypted_and_verifiable(tmp_path, monkeypatch) -> None:
    database, documents, backup_root = configure_backup_paths(monkeypatch, tmp_path)
    backup = backups.create_backup()
    assert backup.parent == backup_root
    assert backup.suffix == ".oribak"
    assert b"private backup content" not in backup.read_bytes()
    manifest = backups.verify_backup(backup)
    assert manifest["format"] == "orinoco-backup-v1"
    assert manifest["document_file_count"] == 1
    assert manifest["session_secret_included"] is True


def test_backup_rejects_wrong_encryption_key(tmp_path, monkeypatch) -> None:
    configure_backup_paths(monkeypatch, tmp_path)
    backup = backups.create_backup()
    monkeypatch.setenv("ORINOCO_BACKUP_KEY", backups.generate_key())
    with pytest.raises(Exception, match="|"):
        backups.verify_backup(backup)


def test_backup_restore_recovers_database_documents_and_session_secret(tmp_path, monkeypatch) -> None:
    database, documents, _ = configure_backup_paths(monkeypatch, tmp_path)
    backup = backups.create_backup()
    (documents / "private" / "note.txt").write_text("changed after backup", encoding="utf-8")
    with sqlite3.connect(database) as connection:
        connection.execute("DELETE FROM users")
    manifest = backups.restore_backup(backup, confirm=True)
    assert manifest["format"] == "orinoco-backup-v1"
    assert (documents / "private" / "note.txt").read_text(encoding="utf-8") == "private backup content"
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT username FROM users").fetchone()[0] == "backup-user"
    assert Path(str(database) + ".pre-restore").exists()


def test_restore_requires_explicit_confirmation(tmp_path, monkeypatch) -> None:
    configure_backup_paths(monkeypatch, tmp_path)
    backup = backups.create_backup()
    with pytest.raises(backups.BackupError, match="stopped Orinoco"):
        backups.restore_backup(backup)


def test_backup_detects_tampered_ciphertext(tmp_path, monkeypatch) -> None:
    configure_backup_paths(monkeypatch, tmp_path)
    backup = backups.create_backup()
    data = bytearray(backup.read_bytes())
    data[len(backups.MAGIC) + 12 + 3] ^= 0x01
    backup.write_bytes(data)
    with pytest.raises(Exception):
        backups.verify_backup(backup)
