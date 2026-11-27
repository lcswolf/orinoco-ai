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
    secret_path = tmp_path / "data" / ".session_secret"
    secret_path.write_text("current-session-secret-before-restore", encoding="utf-8")
    (documents / "private" / "note.txt").write_text("changed after backup", encoding="utf-8")
    with sqlite3.connect(database) as connection:
        connection.execute("DELETE FROM users")
    manifest = backups.restore_backup(backup, confirm=True)
    assert manifest["format"] == "orinoco-backup-v1"
    assert (documents / "private" / "note.txt").read_text(encoding="utf-8") == "private backup content"
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT username FROM users").fetchone()[0] == "backup-user"
    assert Path(str(database) + ".pre-restore").exists()
    assert secret_path.read_text(encoding="utf-8") == "test-session-secret-value-which-is-long-enough"
    assert Path(str(secret_path) + ".pre-restore").read_text(encoding="utf-8") == "current-session-secret-before-restore"


def test_restore_requires_explicit_confirmation(tmp_path, monkeypatch) -> None:
    configure_backup_paths(monkeypatch, tmp_path)
    backup = backups.create_backup()
    with pytest.raises(backups.BackupError, match="after stopping Orinoco"):
        backups.restore_backup(backup)


def test_decrypt_rejects_oversized_backup_before_creating_plaintext(tmp_path) -> None:
    """Reject oversized ciphertext from its metadata before staging any plaintext."""
    source = tmp_path / "oversized.oribak"
    # Sparse allocation exercises the size guard without consuming disk space.
    with source.open("wb") as handle:
        handle.truncate(backups.MAX_ENCRYPTED_BACKUP_BYTES + 1)
    destination = tmp_path / "decrypted.tar.gz"

    with pytest.raises(backups.BackupError, match="encrypted file safety limit"):
        backups._decrypt_file(source, destination, b"x" * 32)

    assert not destination.exists()


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

        def get_object(self, **kwargs):
            from io import BytesIO

            item = self.objects[(kwargs["Bucket"], kwargs["Key"])]
            return {"Body": BytesIO(item["body"])}

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


def test_remote_backup_upload_hashes_downloaded_object_bytes(tmp_path, monkeypatch) -> None:
    """Reject altered remote bytes even when the object metadata claims the expected hash."""
    import sys
    from io import BytesIO
    from types import SimpleNamespace

    configure_backup_paths(monkeypatch, tmp_path)
    backup = backups.create_backup()
    monkeypatch.setenv("ORINOCO_BACKUP_S3_ENDPOINT", "https://objects.example.test")
    monkeypatch.setenv("ORINOCO_BACKUP_S3_BUCKET", "private-orinoco")
    monkeypatch.setenv("ORINOCO_BACKUP_S3_ACCESS_KEY_ID", "test-access")
    monkeypatch.setenv("ORINOCO_BACKUP_S3_SECRET_ACCESS_KEY", "test-secret")

    class AlteredRemoteS3:
        """Return modified object bytes while retaining the original metadata."""

        def put_object(self, **kwargs):
            self.body = kwargs["Body"].read()
            self.metadata = kwargs["Metadata"]

        def head_object(self, **kwargs):
            return {"ContentLength": len(self.body), "Metadata": self.metadata}

        def get_object(self, **kwargs):
            altered = bytearray(self.body)
            altered[-1] ^= 1
            return {"Body": BytesIO(altered)}

    fake_s3 = AlteredRemoteS3()
    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(client=lambda *args, **kwargs: fake_s3))
    with pytest.raises(backups.BackupError, match="downloaded object SHA-256"):
        backups.upload_backup(backup)


def test_remote_backup_upload_rejects_symlink_source(tmp_path, monkeypatch) -> None:
    """Do not follow symbolic links when selecting a backup file for upload."""
    configure_backup_paths(monkeypatch, tmp_path)
    backup = backups.create_backup()
    link = backup.with_name("linked-backup.oribak")
    link.symlink_to(backup)
    monkeypatch.setenv("ORINOCO_BACKUP_S3_ENDPOINT", "https://objects.example.test")
    monkeypatch.setenv("ORINOCO_BACKUP_S3_BUCKET", "private-orinoco")
    monkeypatch.setenv("ORINOCO_BACKUP_S3_ACCESS_KEY_ID", "test-access")
    monkeypatch.setenv("ORINOCO_BACKUP_S3_SECRET_ACCESS_KEY", "test-secret")
    with pytest.raises(backups.BackupError, match="symbolic link"):
        backups.upload_backup(link)


def test_failed_restore_rolls_back_session_secret(tmp_path, monkeypatch) -> None:
    """A late restore failure must not leave the previous session secret replaced."""
    from pathlib import Path

    database, documents, _ = configure_backup_paths(monkeypatch, tmp_path)
    backup = backups.create_backup()
    secret_path = tmp_path / "data" / ".session_secret"
    secret_path.write_text("current-session-secret-that-must-survive-rollback", encoding="utf-8")
    original_chmod = Path.chmod

    def fail_live_secret_chmod(path, mode, *args, **kwargs):
        if path == secret_path:
            raise OSError("simulated session secret permission failure")
        return original_chmod(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "chmod", fail_live_secret_chmod)
    with pytest.raises(OSError, match="simulated session secret"):
        backups.restore_backup(backup, confirm=True)

    assert secret_path.read_text(encoding="utf-8") == "current-session-secret-that-must-survive-rollback"
    assert (documents / "private" / "note.txt").read_text(encoding="utf-8") == "private backup content"
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT username FROM users").fetchone()[0] == "backup-user"


def test_restore_rejects_dangling_recovery_symlink(tmp_path, monkeypatch) -> None:
    """Restore must refuse dangling recovery links before touching live data."""
    database, _, _ = configure_backup_paths(monkeypatch, tmp_path)
    backup = backups.create_backup()
    recovery_path = database.with_suffix(database.suffix + ".pre-restore")
    recovery_path.symlink_to(tmp_path / "missing-recovery-target")

    with pytest.raises(backups.BackupError, match="already exists or is unsafe"):
        backups.restore_backup(backup, confirm=True)

    assert recovery_path.is_symlink()
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT username FROM users").fetchone()[0] == "backup-user"


def test_s3_sdk_failure_is_reported_as_backup_error(tmp_path, monkeypatch) -> None:
    """Network/provider exceptions should produce a safe CLI error, not a traceback with SDK details."""
    import sys
    from types import SimpleNamespace

    configure_backup_paths(monkeypatch, tmp_path)
    backup = backups.create_backup()
    monkeypatch.setenv("ORINOCO_BACKUP_S3_ENDPOINT", "https://objects.example.test")
    monkeypatch.setenv("ORINOCO_BACKUP_S3_BUCKET", "private-orinoco")
    monkeypatch.setenv("ORINOCO_BACKUP_S3_ACCESS_KEY_ID", "test-access")
    monkeypatch.setenv("ORINOCO_BACKUP_S3_SECRET_ACCESS_KEY", "test-secret")

    class BrokenS3:
        """Simulate a provider/network error without contacting a real service."""

        def put_object(self, **kwargs):
            raise RuntimeError("provider request failed with sensitive transport details")

    fake_s3 = BrokenS3()
    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(client=lambda *args, **kwargs: fake_s3))
    with pytest.raises(backups.BackupError, match="upload or remote verification failed"):
        backups.upload_backup(backup)


@pytest.mark.parametrize(
    "member_name",
    [
        "../escape.txt",
        "documents/../../escape.txt",
        "C:/escape.txt",
        "documents\\\\windows-path.txt",
    ],
)
def test_backup_verification_rejects_unsafe_archive_paths(
    tmp_path, monkeypatch, member_name: str
) -> None:
    """Reject traversal and cross-platform path tricks before archive extraction."""
    import io
    import tarfile

    configure_backup_paths(monkeypatch, tmp_path)
    archive = tmp_path / "unsafe.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        payload = b"must not be extracted"
        member = tarfile.TarInfo(member_name)
        member.size = len(payload)
        tar.addfile(member, io.BytesIO(payload))

    encrypted = tmp_path / "unsafe.oribak"
    backups._encrypt_file(archive, encrypted, backups._backup_key())

    with pytest.raises(backups.BackupError, match="unsafe"):
        backups.verify_backup(encrypted)


def test_backup_verification_rejects_archive_symlinks(tmp_path, monkeypatch) -> None:
    """A validly encrypted archive must not be able to restore a symbolic link."""
    import tarfile

    configure_backup_paths(monkeypatch, tmp_path)
    archive = tmp_path / "symlink.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        member = tarfile.TarInfo("documents/private/outside-link")
        member.type = tarfile.SYMTYPE
        member.linkname = "../../outside.txt"
        tar.addfile(member)

    encrypted = tmp_path / "symlink.oribak"
    backups._encrypt_file(archive, encrypted, backups._backup_key())

    with pytest.raises(backups.BackupError, match="unsupported filesystem entry"):
        backups.verify_backup(encrypted)


def test_backup_verification_rejects_duplicate_archive_paths(tmp_path, monkeypatch) -> None:
    """Duplicate names are rejected instead of allowing ambiguous overwrite order."""
    import io
    import tarfile

    configure_backup_paths(monkeypatch, tmp_path)
    archive = tmp_path / "duplicate.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for payload in (b"first", b"second"):
            member = tarfile.TarInfo("documents/private/note.txt")
            member.size = len(payload)
            tar.addfile(member, io.BytesIO(payload))

    encrypted = tmp_path / "duplicate.oribak"
    backups._encrypt_file(archive, encrypted, backups._backup_key())

    with pytest.raises(backups.BackupError, match="duplicate archive paths"):
        backups.verify_backup(encrypted)


def test_backup_verification_rejects_empty_sqlite_database(tmp_path, monkeypatch) -> None:
    """SQLite integrity alone must not allow an empty, unusable backup database."""
    import io
    import json
    import tarfile

    configure_backup_paths(monkeypatch, tmp_path)
    empty_database = tmp_path / "empty.sqlite3"
    sqlite3.connect(empty_database).close()
    archive = tmp_path / "empty-database.tar.gz"
    manifest = json.dumps({"format": "orinoco-backup-v1"}).encode("utf-8")

    with tarfile.open(archive, "w:gz") as tar:
        for name, payload in (
            ("database.sqlite3", empty_database.read_bytes()),
            ("manifest.json", manifest),
        ):
            member = tarfile.TarInfo(name)
            member.size = len(payload)
            tar.addfile(member, io.BytesIO(payload))

    encrypted = tmp_path / "empty-database.oribak"
    backups._encrypt_file(archive, encrypted, backups._backup_key())

    with pytest.raises(backups.BackupError, match="missing required Orinoco tables"):
        backups.verify_backup(encrypted)


def test_backup_verification_rejects_future_database_schema(tmp_path, monkeypatch) -> None:
    """A backup from a newer Orinoco schema must not be treated as restorable here."""
    database, _, _ = configure_backup_paths(monkeypatch, tmp_path)
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA user_version = 99")

    backup = backups.create_backup()

    with pytest.raises(backups.BackupError, match="newer than this Orinoco build"):
        backups.verify_backup(backup)


def test_backup_verification_rejects_foreign_key_violations(tmp_path, monkeypatch) -> None:
    """A valid SQLite file with orphaned application rows is not a valid backup."""
    database, _, _ = configure_backup_paths(monkeypatch, tmp_path)
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """
            INSERT INTO conversations (user_id, title, created_at, updated_at)
            VALUES (999999, 'orphaned', '2026-11-24T00:00:00+00:00', '2026-11-24T00:00:00+00:00')
            """
        )

    backup = backups.create_backup()

    with pytest.raises(backups.BackupError, match="foreign-key consistency errors"):
        backups.verify_backup(backup)


def test_backup_snapshot_includes_committed_wal_data(tmp_path, monkeypatch) -> None:
    """The online SQLite snapshot must include committed rows still in the WAL."""
    database, _, _ = configure_backup_paths(monkeypatch, tmp_path)
    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("CREATE TABLE wal_probe (value TEXT NOT NULL)")
        connection.execute("INSERT INTO wal_probe (value) VALUES ('committed-in-wal')")
        connection.commit()
        wal_path = Path(str(database) + "-wal")
        assert wal_path.exists()

        backup = backups.create_backup()
    finally:
        connection.close()

    changed = sqlite3.connect(database)
    try:
        changed.execute("DROP TABLE wal_probe")
    finally:
        changed.close()

    backups.restore_backup(backup, confirm=True)

    with sqlite3.connect(database) as restored:
        assert restored.execute("SELECT value FROM wal_probe").fetchone()[0] == "committed-in-wal"


def test_backup_verification_rejects_negative_database_schema_version(tmp_path, monkeypatch) -> None:
    """Negative SQLite user_version values are not valid legacy schemas."""
    database, _, _ = configure_backup_paths(monkeypatch, tmp_path)
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA user_version = -1")

    backup = backups.create_backup()

    with pytest.raises(backups.BackupError, match="invalid negative schema version"):
        backups.verify_backup(backup)


def test_backup_verification_requires_version_six_preference_tables(tmp_path, monkeypatch) -> None:
    """A current-schema backup missing v6 tables must not be accepted as complete."""
    database, _, _ = configure_backup_paths(monkeypatch, tmp_path)
    with sqlite3.connect(database) as connection:
        connection.execute("DROP TABLE user_preferences")

    backup = backups.create_backup()

    with pytest.raises(backups.BackupError, match="missing required Orinoco tables"):
        backups.verify_backup(backup)


def test_legacy_v5_backup_can_be_verified_for_additive_upgrade(tmp_path, monkeypatch) -> None:
    """A supported v5 snapshot need not contain tables introduced by schema v6."""
    database, _, _ = configure_backup_paths(monkeypatch, tmp_path)
    with sqlite3.connect(database) as connection:
        connection.execute("DROP TABLE user_preferences")
        connection.execute("DROP TABLE assistant_persona")
        connection.execute("PRAGMA user_version = 5")

    backup = backups.create_backup()

    manifest = backups.verify_backup(backup)

    assert manifest["format"] == "orinoco-backup-v1"
