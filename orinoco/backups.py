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
DEFAULT_BACKUP_ROOT = Path("/home/container/backups")
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
    """Encrypt a file incrementally with authenticated AES-256-GCM."""
    nonce = secrets.token_bytes(12)
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    with source.open("rb") as input_file, destination.open("xb") as output_file:
        output_file.write(MAGIC)
        output_file.write(nonce)
        while chunk := input_file.read(CHUNK_SIZE):
            output_file.write(encryptor.update(chunk))
        output_file.write(encryptor.finalize())
        output_file.write(encryptor.tag)
        output_file.flush()
        os.fsync(output_file.fileno())
    destination.chmod(0o600)


def _decrypt_file(source: Path, destination: Path, key: bytes) -> None:
    """Authenticate and decrypt a backup incrementally before it can be restored."""
    size = source.stat().st_size
    header_size = len(MAGIC) + 12
    if size < header_size + 16:
        raise BackupError("Backup file is too small or incomplete.")
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
            with destination.open("xb") as output_file:
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
            destination.unlink(missing_ok=True)
            raise BackupError("Backup authentication failed: wrong key or damaged file.") from exc
        except Exception:
            destination.unlink(missing_ok=True)
            raise
    destination.chmod(0o600)


def _session_secret_path() -> Path:
    """Resolve the persistent session secret using the same default as auth."""
    return Path(os.environ.get("ORINOCO_SESSION_SECRET_PATH", str(get_database_path().parent / ".session_secret")))


def _copy_database_snapshot(destination: Path) -> None:
    """Use SQLite's online backup API so committed WAL data is included safely."""
    source_path = get_database_path()
    if not source_path.is_file():
        raise BackupError(f"Database file does not exist: {source_path}")
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
    database_snapshot = staging / "database.sqlite3"
    _copy_database_snapshot(database_snapshot)

    document_root = get_document_root()
    document_count = 0
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
    backup_root = Path(os.environ.get("ORINOCO_BACKUP_PATH", str(DEFAULT_BACKUP_ROOT)))
    backup_root.mkdir(parents=True, exist_ok=True)
    backup_root.chmod(0o700)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output = destination or backup_root / f"orinoco-{timestamp}.oribak"
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="orinoco-backup-") as temporary:
        staging = Path(temporary) / "staging"
        staging.mkdir()
        archive = Path(temporary) / "backup.tar.gz"
        _build_archive(staging, archive)
        _encrypt_file(archive, output, key)
    return output


def _read_archive(archive: Path, extraction_root: Path) -> dict[str, object]:
    """Validate every archive member and extract only regular, expected files."""
    seen: set[str] = set()
    total_bytes = 0
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar:
            if len(seen) >= MAX_ARCHIVE_FILES:
                raise BackupError("Backup contains too many archive entries.")
            total_bytes += max(0, member.size)
            if total_bytes > MAX_ARCHIVE_BYTES:
                raise BackupError("Backup expands beyond the 2 GiB safety limit.")
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or not path.parts:
                raise BackupError("Backup contains an unsafe file path.")
            name = path.as_posix()
            if name in seen:
                raise BackupError("Backup contains duplicate archive paths.")
            seen.add(name)
            if member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
                raise BackupError("Backup contains an unsupported filesystem entry.")
            if member.isdir():
                if path.parts[0] not in ALLOWED_DIRECTORIES:
                    raise BackupError("Backup contains an unexpected directory.")
                (extraction_root / Path(*path.parts)).mkdir(parents=True, exist_ok=True)
                continue
            if name not in ALLOWED_FILES and path.parts[0] != "documents":
                raise BackupError("Backup contains an unexpected file.")
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
    manifest = json.loads((extraction_root / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("format") != "orinoco-backup-v1":
        raise BackupError("Backup manifest version is not supported.")
    return manifest


def verify_backup(backup_path: Path) -> dict[str, object]:
    """Decrypt, authenticate, inspect and integrity-check a backup without restoring it."""
    key = _backup_key()
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
    database_path = get_database_path()
    document_root = get_document_root()
    secret_path = _session_secret_path()

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
        if database_backup.exists():
            raise BackupError(f"Recovery file already exists: {database_backup}")
        if database_path.exists():
            shutil.copy2(database_path, database_backup)
        old_documents = document_root.with_name(document_root.name + ".pre-restore")
        if old_documents.exists():
            raise BackupError(f"Recovery directory already exists: {old_documents}")

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
            raise

    return manifest


def main() -> int:
    """Run the backup CLI: generate-key, create, verify or confirmed restore."""
    parser = argparse.ArgumentParser(description="Encrypted Orinoco backup and recovery tools")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("generate-key", help="print a new 256-bit backup key")
    commands.add_parser("create", help="create an encrypted backup")
    verify = commands.add_parser("verify", help="authenticate and inspect a backup")
    verify.add_argument("backup", type=Path)
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
        elif args.command == "restore":
            print(json.dumps(restore_backup(args.backup, confirm=args.confirm), indent=2))
        return 0
    except (BackupError, OSError, sqlite3.Error, tarfile.TarError, json.JSONDecodeError) as exc:
        print(f"Orinoco backup error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
