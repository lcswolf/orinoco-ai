"""Read-only, bounded operational checks for the admin diagnostics screen."""
from __future__ import annotations

import os
import shutil
import sqlite3
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
