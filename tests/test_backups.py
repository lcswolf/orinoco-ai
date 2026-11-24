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
    with pytest.raises(backups.BackupError, match="authentication failed"):
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
    with pytest.raises(backups.BackupError, match="after stopping Orinoco"):
        backups.restore_backup(backup)


def test_backup_detects_tampered_ciphertext(tmp_path, monkeypatch) -> None:
    configure_backup_paths(monkeypatch, tmp_path)
    backup = backups.create_backup()
    data = bytearray(backup.read_bytes())
    data[len(backups.MAGIC) + 12 + 3] ^= 0x01
    backup.write_bytes(data)
    with pytest.raises(backups.BackupError, match="authentication failed"):
        backups.verify_backup(backup)



def test_backup_refuses_document_symlinks(tmp_path, monkeypatch) -> None:
    _, documents, _ = configure_backup_paths(monkeypatch, tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("must never be included", encoding="utf-8")
    (documents / "private" / "outside-link.txt").symlink_to(outside)
    with pytest.raises(backups.BackupError, match="symbolic link"):
        backups.create_backup()



def test_encrypted_backup_uploads_and_verifies_remote_checksum(tmp_path, monkeypatch) -> None:
    import sys
    from types import SimpleNamespace

    configure_backup_paths(monkeypatch, tmp_path)
    backup = backups.create_backup()
    monkeypatch.setenv("ORINOCO_BACKUP_S3_ENDPOINT", "https://objects.example.test")
    monkeypatch.setenv("ORINOCO_BACKUP_S3_BUCKET", "private-orinoco")
    monkeypatch.setenv("ORINOCO_BACKUP_S3_ACCESS_KEY_ID", "test-access")
    monkeypatch.setenv("ORINOCO_BACKUP_S3_SECRET_ACCESS_KEY", "test-secret")

    class FakeS3:
        """Small in-memory S3 client double; no network access is performed."""

        def __init__(self):
            self.objects = {}

        def put_object(self, **kwargs):
            self.objects[(kwargs["Bucket"], kwargs["Key"])] = {
                "body": kwargs["Body"].read(),
                "metadata": kwargs["Metadata"],
            }

        def head_object(self, **kwargs):
            item = self.objects[(kwargs["Bucket"], kwargs["Key"])]
            return {
                "ContentLength": len(item["body"]),
                "Metadata": item["metadata"],
            }

    fake_s3 = FakeS3()
    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(client=lambda *args, **kwargs: fake_s3))
    result = backups.upload_backup(backup)
    assert result["verified"] is True
    assert result["bucket"] == "private-orinoco"
    assert result["key"].endswith(backup.name)
    assert result["size_bytes"] == backup.stat().st_size


def test_remote_backup_upload_requires_https_endpoint(tmp_path, monkeypatch) -> None:
    import sys
    from types import SimpleNamespace

    configure_backup_paths(monkeypatch, tmp_path)
    backup = backups.create_backup()
    monkeypatch.setenv("ORINOCO_BACKUP_S3_ENDPOINT", "http://objects.example.test")
    monkeypatch.setenv("ORINOCO_BACKUP_S3_BUCKET", "private-orinoco")
    monkeypatch.setenv("ORINOCO_BACKUP_S3_ACCESS_KEY_ID", "test-access")
    monkeypatch.setenv("ORINOCO_BACKUP_S3_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(client=lambda *args, **kwargs: None))
    with pytest.raises(backups.BackupError, match="HTTPS"):
        backups.upload_backup(backup)


def test_remote_backup_upload_rejects_checksum_mismatch(tmp_path, monkeypatch) -> None:
    import sys
    from types import SimpleNamespace

    configure_backup_paths(monkeypatch, tmp_path)
    backup = backups.create_backup()
    monkeypatch.setenv("ORINOCO_BACKUP_S3_ENDPOINT", "https://objects.example.test")
    monkeypatch.setenv("ORINOCO_BACKUP_S3_BUCKET", "private-orinoco")
    monkeypatch.setenv("ORINOCO_BACKUP_S3_ACCESS_KEY_ID", "test-access")
    monkeypatch.setenv("ORINOCO_BACKUP_S3_SECRET_ACCESS_KEY", "test-secret")

    class MismatchedS3:
        """Simulate a remote object whose checksum metadata is incorrect."""

        def put_object(self, **kwargs):
            self.bucket, self.key = kwargs["Bucket"], kwargs["Key"]

        def head_object(self, **kwargs):
            return {"ContentLength": backup.stat().st_size, "Metadata": {"sha256": "wrong"}}

    fake_s3 = MismatchedS3()
    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(client=lambda *args, **kwargs: fake_s3))
    with pytest.raises(backups.BackupError, match="verification failed"):
        backups.upload_backup(backup)
