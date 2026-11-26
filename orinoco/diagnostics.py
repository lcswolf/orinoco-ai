"""Read-only, bounded operational checks for the admin diagnostics screen."""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import sqlite3
import stat
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from orinoco import __version__
from orinoco.db import get_database_path

OLLAMA_API_BASE = "http://127.0.0.1:11434"


def _result(name: str, status: str, summary: str, **details: Any) -> dict[str, Any]:
    return {"name": name, "status": status, "summary": summary, **details}


def check_database() -> dict[str, Any]:
    """Run SQLite quick_check using a read-only connection; never migrate or write."""
    path = get_database_path()
    if not path.exists():
        return _result("database", "fail", "The database file does not exist.")
    try:
        uri = path.resolve().as_uri() + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=2)
        try:
            row = connection.execute("PRAGMA quick_check(1)").fetchone()
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        finally:
            connection.close()
        if not row or row[0] != "ok":
            return _result("database", "fail", "SQLite reported an integrity problem.")
        return _result("database", "pass", "Database is readable and passed its integrity check.", schema_version=version)
    except (OSError, sqlite3.Error, ValueError):
        return _result("database", "fail", "Database could not be checked.")


def check_storage() -> list[dict[str, Any]]:
    """Check expected persistent directories and available disk space without writing."""
    root = get_database_path().parent
    checks: list[dict[str, Any]] = []
    for name in ("data", "logs", "documents", "backups", "models"):
        path = root if name == "data" else root / name
        try:
            exists = path.is_dir()
            writable = exists and os.access(path, os.W_OK)
            status = "pass" if exists and writable else ("warning" if exists else "warning")
            summary = "Directory exists and is writable." if exists and writable else (
                "Directory exists but is not writable." if exists else "Directory has not been created yet."
            )
            checks.append(_result(f"storage_{name}", status, summary))
        except OSError:
            checks.append(_result(f"storage_{name}", "warning", "Directory status could not be checked."))
    try:
        usage = shutil.disk_usage(root if root.exists() else root.parent)
        checks.append(_result(
            "disk_space",
            "pass" if usage.free >= 512 * 1024 * 1024 else "warning",
            "Available disk space checked.",
            free_bytes=usage.free,
        ))
    except OSError:
        checks.append(_result("disk_space", "warning", "Available disk space could not be checked."))
    return checks


async def check_ollama(model: str | None = None) -> dict[str, Any]:
    """Check only the local Ollama API; never trigger model downloads or inference."""
    selected = model or os.environ.get("AI_MODEL", "qwen2.5:1.5b")
    try:
        async with httpx.AsyncClient(timeout=2.0, trust_env=False) as client:
            response = await client.get(f"{OLLAMA_API_BASE}/api/tags")
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
            return _result("ollama", "fail", "The local model service returned an invalid response.")
        available = {
            item.get("name") or item.get("model")
            for item in payload["models"]
            if isinstance(item, dict)
        }
        if selected not in available:
            return _result("ollama", "warning", "The model service is running, but the selected model is not installed.", selected_model=selected)
        return _result("ollama", "pass", "The model service is running and the selected model is installed.", selected_model=selected)
    except (httpx.HTTPError, ValueError):
        return _result("ollama", "fail", "The local model service could not be reached.")


async def run_diagnostics() -> dict[str, Any]:
    """Collect safe, read-only checks and a minimal version summary."""
    checks = [check_database(), *check_storage(), await check_ollama()]
    overall = "fail" if any(item["status"] == "fail" for item in checks) else (
        "warning" if any(item["status"] == "warning" for item in checks) else "pass"
    )
    return {
        "status": overall,
        "version": __version__,
        "checks": checks,
    }



def _safe_recent_log_events(path: Path, limit_bytes: int = 256 * 1024) -> tuple[str, bool]:
    """Export only allowlisted operational metadata, never free-form log messages."""
    if path.is_symlink() or path.parent.is_symlink():
        return "", False
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return "", False
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            return "", False
        truncated = metadata.st_size > limit_bytes
        if truncated:
            os.lseek(descriptor, metadata.st_size - limit_bytes, os.SEEK_SET)
        chunks: list[bytes] = []
        remaining = limit_bytes
        while remaining > 0:
            chunk = os.read(descriptor, min(65536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks).decode("utf-8", errors="replace")
    finally:
        os.close(descriptor)

    safe_records: list[str] = []
    for line in raw.splitlines()[-500:]:
        try:
            record = json.loads(line)
        except (TypeError, ValueError):
            continue
        if not isinstance(record, dict) or not record.get("event_code"):
            continue
        safe = {
            key: record[key]
            for key in ("timestamp", "level", "logger", "event_code", "request_id")
            if isinstance(record.get(key), (str, int, float))
        }
        # Event codes are the useful troubleshooting signal. Free-form message
        # and exception fields are deliberately excluded to prevent user-data leaks.
        event_code = safe.get("event_code")
        if not isinstance(event_code, str) or not re.fullmatch(r"[a-z0-9_.-]{1,80}", event_code):
            continue
        safe_records.append(json.dumps(safe, ensure_ascii=True, separators=(",", ":")))
    return "\n".join(safe_records) + ("\n" if safe_records else ""), truncated


async def build_support_bundle() -> bytes:
    """Build a bounded in-memory ZIP containing diagnostics and safe event metadata."""
    report = await run_diagnostics()
    log_path = get_database_path().parent / "logs" / "orinoco.log"
    events, truncated = _safe_recent_log_events(log_path)
    created = datetime.now(timezone.utc).isoformat()
    manifest = {
        "created_at": created,
        "format_version": 1,
        "files": ["diagnostics.json", "logs/recent-events.jsonl", "manifest.json"],
        "log_window_truncated": truncated,
        "privacy": (
            "No conversations, prompts, replies, memories, documents, database files, "
            "environment values, credentials, free-form log messages or exception text are included."
        ),
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.writestr("diagnostics.json", json.dumps(report, ensure_ascii=True, indent=2))
        archive.writestr("logs/recent-events.jsonl", events)
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=True, indent=2))
    bundle = output.getvalue()
    if len(bundle) > 512 * 1024:
        raise RuntimeError("The generated support bundle exceeded its size limit.")
    return bundle
