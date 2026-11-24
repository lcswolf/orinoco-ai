"""Encrypted, verifiable backups for Orinoco's persistent user data.

Backups contain a transaction-consistent SQLite snapshot, uploaded documents,
and the persistent session-signing file. Large Ollama model weights are
intentionally excluded; the selected model name is recorded in the manifest.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import secrets
import shutil
import sqlite3
import struct
import sys
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from orinoco import __version__
from orinoco.db import get_database_path
from orinoco.documents.storage import get_document_root

MAGIC = b"ORINOCO-BACKUP-1\n"
CHUNK_SIZE = 1024 * 1024
MAX_ARCHIVE_FILES = 100_000
MAX_ARCHIVE_BYTES = 2 * 1024 * 1024 * 1024
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_SESSION_SECRET_BYTES = 4 * 1024
MAX_DOCUMENT_FILE_BYTES = 10 * 1024 * 1024
DEFAULT_BACKUP_ROOT = Path("/home/container/data/backups")
DEFAULT_SECRET_PATH = Path("/home/container/data/.session_secret")
ALLOWED_FILES = {"database.sqlite3", "manifest.json", "session_secret"}
ALLOWED_DIRECTORIES = {"documents"}


class BackupError(RuntimeError):
    """Raised when an encrypted backup cannot be created, verified or restored."""


def _backup_key() -> bytes:
    """Read the 32-byte URL-safe base64 encryption key from the environment."""
    encoded = os.environ.get("ORINOCO_BACKUP_KEY", "").strip()
    if not encoded:
        raise BackupError(
            "ORINOCO_BACKUP_KEY is missing. Generate a key with "
            "'python -m orinoco.backups generate-key' and store it securely."
        )
    try:
        key = base64.urlsafe_b64decode(encoded.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise BackupError("ORINOCO_BACKUP_KEY is not valid URL-safe base64.") from exc
    if len(key) != 32:
        raise BackupError("ORINOCO_BACKUP_KEY must decode to exactly 32 bytes.")
    return key


def generate_key() -> str:
    """Generate a new encryption key; print it once and store it outside the VPS."""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")


def _encrypt_file(source: Path, destination: Path, key: bytes) -> None:
    """Encrypt a file incrementally with authenticated AES-256-GCM.

    The destination is created with owner-only permissions and removed if
    encryption fails, so partial backup files are never mistaken for complete
    backups on a later run.
    """
    nonce = secrets.token_bytes(12)
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    try:
        # Open the source first so a missing/unreadable source cannot leak the
        # newly-created destination descriptor.
        with source.open("rb") as input_file:
            descriptor = os.open(
                destination,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            with os.fdopen(descriptor, "wb") as output_file:
                output_file.write(MAGIC)
                output_file.write(nonce)
                while chunk := input_file.read(CHUNK_SIZE):
                    output_file.write(encryptor.update(chunk))
                output_file.write(encryptor.finalize())
                output_file.write(encryptor.tag)
                output_file.flush()
                os.fsync(output_file.fileno())
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    destination.chmod(0o600)

def _decrypt_file(source: Path, destination: Path, key: bytes) -> None:
    """Authenticate and decrypt a backup incrementally before it can be restored."""
    size = source.stat().st_size
    header_size = len(MAGIC) + 12
    if size < header_size + 16:
        raise BackupError("Backup file is too small or incomplete.")
    created = False
    with source.open("rb") as input_file:
        if input_file.read(len(MAGIC)) != MAGIC:
            raise BackupError("This is not a supported Orinoco backup file.")
        nonce = input_file.read(12)
        input_file.seek(-16, os.SEEK_END)
        tag = input_file.read(16)
        input_file.seek(header_size)
        remaining = size - header_size - 16
        decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
        try:
            descriptor = os.open(
                destination,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            created = True
            with os.fdopen(descriptor, "wb") as output_file:
                while remaining:
                    chunk = input_file.read(min(CHUNK_SIZE, remaining))
                    if not chunk:
                        raise BackupError("Backup file ended unexpectedly.")
                    remaining -= len(chunk)
                    output_file.write(decryptor.update(chunk))
                output_file.write(decryptor.finalize())
                output_file.flush()
                os.fsync(output_file.fileno())
        except InvalidTag as exc:
            if created:
                destination.unlink(missing_ok=True)
            raise BackupError("Backup authentication failed: wrong key or damaged file.") from exc
        except Exception:
            # Do not delete a pre-existing destination if O_EXCL failed.
            if created:
                destination.unlink(missing_ok=True)
            raise
    destination.chmod(0o600)

def _validate_backup_source(backup_path: Path) -> Path:
    """Require an existing regular encrypted backup file and reject symlinks."""
    path = Path(backup_path).expanduser()
    if path.is_symlink():
        raise BackupError("Backup source must be a regular file, not a symbolic link.")
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise BackupError("Backup source does not exist or cannot be resolved safely.") from exc
    if not resolved.is_file() or resolved.suffix != ".oribak":
        raise BackupError("Backup source must be an existing encrypted .oribak file.")
    return resolved


def _session_secret_path() -> Path:
    """Resolve the persistent session secret using the same default as auth."""
    return Path(os.environ.get("ORINOCO_SESSION_SECRET_PATH", str(get_database_path().parent / ".session_secret")))


def _copy_database_snapshot(destination: Path) -> None:
    """Use SQLite's online backup API so committed WAL data is included safely."""
    source_path = get_database_path()
    if source_path.is_symlink() or not source_path.is_file():
        raise BackupError("The configured database must be an existing regular file, not a symbolic link.")
    source = sqlite3.connect(source_path, timeout=30)
    target = sqlite3.connect(destination)
    try:
        source.backup(target)
        result = target.execute("PRAGMA integrity_check").fetchone()
        if not result or result[0] != "ok":
            raise BackupError("SQLite integrity check failed while creating backup.")
    finally:
        target.close()
        source.close()
    destination.chmod(0o600)


def _build_archive(staging: Path, archive: Path) -> dict[str, object]:
    """Stage a consistent database, document tree, session secret and manifest."""
    from orinoco.documents.storage import document_storage_lock

    database_snapshot = staging / "database.sqlite3"
    document_count = 0
    # A cross-process lock keeps the SQLite snapshot and uploaded files in sync
    # with concurrent uploads/deletions performed by the web application.
    with document_storage_lock():
        _copy_database_snapshot(database_snapshot)
        document_root = get_document_root()
        if document_root.exists():
            if document_root.is_symlink():
                raise BackupError("Document storage must not be a symbolic link.")
            # Reject links before copytree so a link cannot make the backup include
            # files from outside Orinoco's private document directory.
            if any(item.is_symlink() for item in document_root.rglob("*")):
                raise BackupError("Document storage contains a symbolic link.")
            target_documents = staging / "documents"
            shutil.copytree(document_root, target_documents, symlinks=False)
            document_count = sum(1 for item in target_documents.rglob("*") if item.is_file())
            for item in target_documents.rglob("*"):
                if item.is_symlink():
                    raise BackupError("Document storage contains a symbolic link.")
        else:
            (staging / "documents").mkdir()

    secret_path = _session_secret_path()
    if secret_path.is_symlink():
        raise BackupError("The session secret path must not be a symbolic link.")
    if secret_path.is_file():
        shutil.copy2(secret_path, staging / "session_secret")
    elif os.environ.get("ORINOCO_SECRET_KEY"):
        # When the secret is supplied by the environment it cannot be safely
        # copied from the process; the encrypted backup records this dependency.
        pass

    manifest: dict[str, object] = {
        "format": "orinoco-backup-v1",
        "created_at": datetime.now(UTC).isoformat(),
        "orinoco_version": __version__,
        "database_bytes": database_snapshot.stat().st_size,
        "document_file_count": document_count,
        "session_secret_included": (staging / "session_secret").exists(),
        "external_session_secret_configured": bool(os.environ.get("ORINOCO_SECRET_KEY")),
        "selected_model": os.environ.get("AI_MODEL", "qwen2.5:1.5b"),
        "model_weights_included": False,
        "note": "Restore the same application secrets separately if configured through environment variables.",
    }
    (staging / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    with tarfile.open(archive, "w:gz") as tar:
        for name in ("database.sqlite3", "documents", "session_secret", "manifest.json"):
            path = staging / name
            if path.exists():
                tar.add(path, arcname=name, recursive=True)
    return manifest


def create_backup(destination: Path | None = None) -> Path:
    """Create an encrypted backup file and return its final path."""
    key = _backup_key()
    backup_root = Path(os.environ.get("ORINOCO_BACKUP_PATH", str(DEFAULT_BACKUP_ROOT))).expanduser()
    if backup_root.is_symlink():
        raise BackupError("The backup directory must not be a symbolic link.")
    backup_root.mkdir(parents=True, exist_ok=True)
    backup_root.chmod(0o700)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output = Path(destination) if destination is not None else backup_root / f"orinoco-{timestamp}.oribak"
    output = output.expanduser()
    if output.is_symlink():
        raise BackupError("The backup destination must not be a symbolic link.")
    if output.suffix != ".oribak":
        raise BackupError("Encrypted backup destinations must use the .oribak extension.")
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="orinoco-backup-") as temporary:
        staging = Path(temporary) / "staging"
        staging.mkdir()
        archive = Path(temporary) / "backup.tar.gz"
        _build_archive(staging, archive)
        _encrypt_file(archive, output, key)
    return output


def _read_archive(archive: Path, extraction_root: Path) -> dict[str, object]:
    """Validate archive paths, member types and expansion limits before extraction."""
    seen: set[str] = set()
    total_bytes = 0
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar:
            if len(seen) >= MAX_ARCHIVE_FILES:
                raise BackupError("Backup contains too many archive entries.")
            total_bytes += max(0, member.size)
            if total_bytes > MAX_ARCHIVE_BYTES:
                raise BackupError("Backup expands beyond the 2 GiB safety limit.")

            # Tar paths are POSIX-style, but restore may run on Windows too.
            # Reject Windows separators, drive/alternate-stream syntax and NULs
            # before converting any archive member into a native Path.
            if not member.name or "\\" in member.name or "\x00" in member.name or ":" in member.name:
                raise BackupError("Backup contains an unsafe cross-platform file path.")
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or not path.parts:
                raise BackupError("Backup contains an unsafe file path.")
            name = path.as_posix()
            if len(name) > 1024:
                raise BackupError("Backup contains an excessively long file path.")
            if name in seen:
                raise BackupError("Backup contains duplicate archive paths.")
            seen.add(name)
            if member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
                raise BackupError("Backup contains an unsupported filesystem entry.")

            if member.isdir():
                if path.parts[0] != "documents":
                    raise BackupError("Backup contains an unexpected directory.")
                (extraction_root / Path(*path.parts)).mkdir(parents=True, exist_ok=True)
                continue

            if name == "documents":
                raise BackupError("The documents archive root must be a directory.")
            if name not in ALLOWED_FILES and path.parts[0] != "documents":
                raise BackupError("Backup contains an unexpected file.")
            if path.parts[0] == "documents" and len(path.parts) < 2:
                raise BackupError("A document file must be inside the documents directory.")
            if name == "manifest.json" and member.size > MAX_MANIFEST_BYTES:
                raise BackupError("Backup manifest exceeds the 1 MiB safety limit.")
            if name == "session_secret" and member.size > MAX_SESSION_SECRET_BYTES:
                raise BackupError("Backup session secret exceeds the 4 KiB safety limit.")
            if path.parts[0] == "documents" and member.size > MAX_DOCUMENT_FILE_BYTES:
                raise BackupError("A stored document exceeds the 10 MiB file safety limit.")

            target = extraction_root / Path(*path.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            source = tar.extractfile(member)
            if source is None:
                raise BackupError("Could not read a backup archive member.")
            with source, target.open("xb") as output:
                shutil.copyfileobj(source, output, length=CHUNK_SIZE)
            target.chmod(0o600)

    required = {"database.sqlite3", "manifest.json"}
    if not required.issubset(seen):
        raise BackupError("Backup is missing required database or manifest files.")
    try:
        manifest = json.loads((extraction_root / "manifest.json").read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackupError("Backup manifest is not valid UTF-8 JSON.") from exc
    if not isinstance(manifest, dict) or manifest.get("format") != "orinoco-backup-v1":
        raise BackupError("Backup manifest version is not supported.")
    return manifest


def verify_backup(backup_path: Path) -> dict[str, object]:
    """Decrypt, authenticate, inspect and integrity-check a backup without restoring it."""
    key = _backup_key()
    backup_path = _validate_backup_source(backup_path)
    with tempfile.TemporaryDirectory(prefix="orinoco-verify-") as temporary:
        archive = Path(temporary) / "backup.tar.gz"
        extracted = Path(temporary) / "extracted"
        extracted.mkdir()
        _decrypt_file(backup_path, archive, key)
        manifest = _read_archive(archive, extracted)
        connection = sqlite3.connect(extracted / "database.sqlite3")
        try:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
        finally:
            connection.close()
        if not integrity or integrity[0] != "ok":
            raise BackupError("Backup database failed SQLite integrity check.")
        return manifest


def restore_backup(backup_path: Path, *, confirm: bool = False) -> dict[str, object]:
    """Restore a verified backup; requires explicit confirmation and a stopped app."""
    if not confirm:
        raise BackupError("Restore is destructive. Re-run with --confirm after stopping Orinoco.")
    key = _backup_key()
    backup_path = _validate_backup_source(backup_path)
    database_path = get_database_path()
    if database_path.is_symlink():
        raise BackupError("The configured database path must not be a symbolic link.")
    document_root = get_document_root()
    secret_path = _session_secret_path()
    if secret_path.is_symlink():
        raise BackupError("The session secret path must not be a symbolic link.")

    with tempfile.TemporaryDirectory(prefix="orinoco-restore-") as temporary:
        root = Path(temporary)
        archive = root / "backup.tar.gz"
        extracted = root / "extracted"
        extracted.mkdir()
        _decrypt_file(backup_path, archive, key)
        manifest = _read_archive(archive, extracted)
        connection = sqlite3.connect(extracted / "database.sqlite3")
        try:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
        finally:
            connection.close()
        if not integrity or integrity[0] != "ok":
            raise BackupError("Backup database failed SQLite integrity check.")

        # Prepare all replacement data before touching the live data directory.
        database_path.parent.mkdir(parents=True, exist_ok=True)
        staged_database = root / "database.restore"
        shutil.copy2(extracted / "database.sqlite3", staged_database)
        staged_documents = root / "documents.restore"
        source_documents = extracted / "documents"
        if source_documents.exists():
            shutil.copytree(source_documents, staged_documents)
        else:
            staged_documents.mkdir()

        database_backup = database_path.with_suffix(database_path.suffix + ".pre-restore")
        database_existed = database_path.exists()
        secret_existed = secret_path.exists()
        secret_backup = secret_path.with_suffix(secret_path.suffix + ".pre-restore")
        old_documents = document_root.with_name(document_root.name + ".pre-restore")

        # Check every recovery destination before creating any of the copies.
        # is_symlink() also detects dangling links, which exists() does not.
        for recovery_path in (database_backup, secret_backup, old_documents):
            if recovery_path.is_symlink() or recovery_path.exists():
                raise BackupError(f"Recovery path already exists or is unsafe: {recovery_path}")

        try:
            if database_existed:
                # Use SQLite online backup so committed WAL data is preserved too.
                _copy_database_snapshot(database_backup)
            if secret_existed:
                shutil.copy2(secret_path, secret_backup)
        except Exception:
            database_backup.unlink(missing_ok=True)
            secret_backup.unlink(missing_ok=True)
            raise

        from orinoco.documents.storage import document_storage_lock

        # Restore is documented as a stopped-app operation; the same file lock
        # also prevents any concurrent document operation during replacement.
        with document_storage_lock():
            try:
                if document_root.exists():
                    document_root.rename(old_documents)
                staged_documents.rename(document_root)
                os.replace(staged_database, database_path)
                for suffix in ("-wal", "-shm"):
                    Path(str(database_path) + suffix).unlink(missing_ok=True)
                if (extracted / "session_secret").exists():
                    secret_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(extracted / "session_secret", secret_path)
                    secret_path.chmod(0o600)
            except Exception:
                if document_root.exists():
                    shutil.rmtree(document_root)
                if old_documents.exists():
                    old_documents.rename(document_root)
                if database_backup.exists():
                    os.replace(database_backup, database_path)
                elif not database_existed:
                    database_path.unlink(missing_ok=True)
                if secret_existed and secret_backup.exists():
                    secret_path.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(secret_backup, secret_path)
                elif not secret_existed:
                    secret_path.unlink(missing_ok=True)
                raise

    return manifest



def _s3_settings() -> dict[str, str]:
    """Validate the S3-compatible destination without exposing its credentials."""
    from urllib.parse import urlsplit

    endpoint = os.environ.get("ORINOCO_BACKUP_S3_ENDPOINT", "").strip()
    bucket = os.environ.get("ORINOCO_BACKUP_S3_BUCKET", "").strip()
    access_key = os.environ.get("ORINOCO_BACKUP_S3_ACCESS_KEY_ID", "").strip()
    secret_key = os.environ.get("ORINOCO_BACKUP_S3_SECRET_ACCESS_KEY", "").strip()
    region = os.environ.get("ORINOCO_BACKUP_S3_REGION", "us-east-1").strip()
    prefix = os.environ.get("ORINOCO_BACKUP_S3_PREFIX", "orinoco").strip().strip("/")

    parsed = urlsplit(endpoint)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise BackupError("The S3 endpoint must be a valid HTTPS URL without embedded credentials or query parameters.")
    if not bucket or not access_key or not secret_key:
        raise BackupError("S3 bucket, access key ID and secret access key must all be configured.")
    if any(part in {".", ".."} for part in PurePosixPath(prefix).parts):
        raise BackupError("The S3 object prefix contains an unsafe path component.")
    if not region:
        raise BackupError("The S3 region must not be blank.")
    return {
        "endpoint": endpoint.rstrip("/"),
        "bucket": bucket,
        "access_key": access_key,
        "secret_key": secret_key,
        "region": region,
        "prefix": prefix,
    }


def upload_backup(backup_path: Path) -> dict[str, object]:
    """Upload one encrypted backup to a private S3-compatible object bucket.

    The endpoint must use HTTPS. The upload uses no public ACL, includes a
    SHA-256 checksum as object metadata, checks the remote size and metadata,
    then downloads and hashes the stored bytes before reporting success.
    """
    try:
        import boto3
    except ImportError as exc:
        raise BackupError("S3-compatible uploads require the boto3 dependency.") from exc

    settings = _s3_settings()
    backup_path = backup_path.expanduser()
    if backup_path.is_symlink():
        raise BackupError("The backup to upload must be an existing regular file, not a symbolic link.")
    try:
        backup_path = backup_path.resolve(strict=True)
    except OSError as exc:
        raise BackupError("The backup to upload must be an existing regular file.") from exc
    if not backup_path.is_file():
        raise BackupError("The backup to upload must be an existing regular file.")
    if backup_path.suffix != ".oribak":
        raise BackupError("Only encrypted .oribak backup files can be uploaded.")

    digest = hashlib.sha256()
    with backup_path.open("rb") as backup_file:
        for chunk in iter(lambda: backup_file.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    checksum = digest.hexdigest()
    object_key = "/".join(
        part for part in (settings["prefix"], backup_path.name) if part
    )

    # Credentials are supplied only to the SDK client; never log or return them.
    try:
        client = boto3.client(
            "s3",
            endpoint_url=settings["endpoint"],
            aws_access_key_id=settings["access_key"],
            aws_secret_access_key=settings["secret_key"],
            region_name=settings["region"],
        )
        with backup_path.open("rb") as backup_file:
            client.put_object(
                Bucket=settings["bucket"],
                Key=object_key,
                Body=backup_file,
                ContentLength=backup_path.stat().st_size,
                ContentType="application/octet-stream",
                Metadata={"sha256": checksum},
            )

        remote = client.head_object(Bucket=settings["bucket"], Key=object_key)
        remote_checksum = (remote.get("Metadata") or {}).get("sha256", "")
        if remote.get("ContentLength") != backup_path.stat().st_size or remote_checksum != checksum:
            raise BackupError("Remote backup verification failed: size or SHA-256 metadata did not match.")

        # Verify the bytes returned by object storage, not just metadata supplied by
        # this client during upload. This detects truncated or altered remote data.
        downloaded = client.get_object(Bucket=settings["bucket"], Key=object_key)
        remote_body = downloaded.get("Body")
        if remote_body is None:
            raise BackupError("Remote backup verification failed: the object body was missing.")
        remote_digest = hashlib.sha256()
        try:
            for chunk in iter(lambda: remote_body.read(CHUNK_SIZE), b""):
                remote_digest.update(chunk)
        finally:
            remote_body.close()
        if remote_digest.hexdigest() != checksum:
            raise BackupError("Remote backup verification failed: downloaded object SHA-256 did not match.")
    except BackupError:
        raise
    except Exception as exc:
        # SDK/network failures must become a concise operational error; never
        # print request objects or credential-bearing configuration.
        raise BackupError("S3-compatible backup upload or remote verification failed.") from exc

    return {
        "bucket": settings["bucket"],
        "key": object_key,
        "size_bytes": backup_path.stat().st_size,
        "sha256": checksum,
        "verified": True,
    }


def main() -> int:
    """Run the backup CLI: generate-key, create, verify or confirmed restore."""
    parser = argparse.ArgumentParser(description="Encrypted Orinoco backup and recovery tools")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("generate-key", help="print a new 256-bit backup key")
    commands.add_parser("create", help="create an encrypted backup")
    verify = commands.add_parser("verify", help="authenticate and inspect a backup")
    verify.add_argument("backup", type=Path)
    upload = commands.add_parser("upload", help="upload an encrypted backup to private S3-compatible storage")
    upload.add_argument("backup", type=Path)
    restore = commands.add_parser("restore", help="restore a backup while Orinoco is stopped")
    restore.add_argument("backup", type=Path)
    restore.add_argument("--confirm", action="store_true", help="confirm destructive restore")
    args = parser.parse_args()

    try:
        if args.command == "generate-key":
            print(generate_key())
        elif args.command == "create":
            print(create_backup())
        elif args.command == "verify":
            print(json.dumps(verify_backup(args.backup), indent=2))
        elif args.command == "upload":
            print(json.dumps(upload_backup(args.backup), indent=2))
        elif args.command == "restore":
            print(json.dumps(restore_backup(args.backup, confirm=args.confirm), indent=2))
        return 0
    except (BackupError, OSError, sqlite3.Error, tarfile.TarError, json.JSONDecodeError) as exc:
        print(f"Orinoco backup error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
