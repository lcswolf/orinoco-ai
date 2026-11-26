"""Privacy-conscious structured logging for Orinoco.

Only operational metadata is emitted. Callers must never pass prompts, chat
content, memory values, document text, credentials or request headers.
"""
from __future__ import annotations

import contextvars
import json
import logging
import os
import re
import stat
import sys
import uuid
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("orinoco_request_id", default="-")

_SECRET_PATTERNS = (
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/-]+=*"), r"\1[REDACTED]"),
    (re.compile(r"(?i)((?:password|passwd|token|secret|api[_-]?key|backup[_-]?key|authorization|cookie)\s*[=:]\s*)[^\s,;]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(https?://)[^/@\s]+:[^/@\s]+@"), r"\1[REDACTED]@"),
)


def redact_text(value: str) -> str:
    """Redact common credential forms from operational messages and tracebacks."""
    redacted = value
    for pattern, replacement in _SECRET_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


class RedactingFilter(logging.Filter):
    """Redact message arguments and exception text before any handler emits them."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            rendered = record.getMessage()
        except Exception:
            rendered = "Log message could not be safely rendered"
        record.msg = redact_text(rendered)
        record.args = ()
        if record.exc_info:
            import traceback

            record.exc_text = redact_text("".join(traceback.format_exception(*record.exc_info)))
            record.exc_info = None
        elif record.exc_text:
            record.exc_text = redact_text(record.exc_text)
        record.request_id = _request_id.get()
        return True


class JsonFormatter(logging.Formatter):
    """Render a small, stable allowlist of structured operational fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name[:80],
            "message": record.getMessage()[:2000],
            "request_id": getattr(record, "request_id", "-"),
        }
        event_code = getattr(record, "event_code", None)
        if isinstance(event_code, str) and re.fullmatch(r"[a-z0-9_.-]{1,80}", event_code):
            payload["event_code"] = event_code
        if record.exc_text:
            payload["exception"] = record.exc_text[-8000:]
        return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


class PrivateRotatingFileHandler(RotatingFileHandler):
    """Rotating UTF-8 log handler that refuses symlinks and restricts file mode."""

    def _open(self):
        flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
        flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(self.baseFilename, flags, 0o600)
        try:
            opened = os.fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode):
                raise OSError("Orinoco log path must be a regular file")
            os.fchmod(descriptor, 0o600)
            return os.fdopen(descriptor, self.mode, encoding=self.encoding, errors=self.errors)
        except Exception:
            os.close(descriptor)
            raise


def _log_directory() -> Path:
    """Place logs beside the configured database on the persistent data volume."""
    from orinoco.db import get_database_path

    return get_database_path().parent / "logs"


def _prepare_log_directory(directory: Path) -> None:
    """Create a private, real directory for logs; never accept a symlink."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if directory.is_symlink() or not directory.is_dir():
        raise OSError("Orinoco log directory must be a real directory")
    os.chmod(directory, 0o700)


def configure_logging() -> None:
    """Configure redacted stdout and bounded persistent logs for Pterodactyl."""
    root = logging.getLogger()
    if getattr(root, "_orinoco_logging_configured", False):
        return

    root.handlers.clear()
    root.setLevel(logging.INFO)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(JsonFormatter())
    console.addFilter(RedactingFilter())
    root.addHandler(console)

    try:
        directory = _log_directory()
        _prepare_log_directory(directory)
        file_handler = PrivateRotatingFileHandler(
            directory / "orinoco.log",
            maxBytes=1024 * 1024,
            backupCount=3,
            encoding="utf-8",
            delay=False,
        )
        file_handler.setFormatter(JsonFormatter())
        file_handler.addFilter(RedactingFilter())
        root.addHandler(file_handler)
    except OSError:
        console.stream.write(
            '{"level":"WARNING","logger":"orinoco.logging",'
            '"message":"Persistent log file unavailable; using console logging only"}\n'
        )
        console.flush()

    root._orinoco_logging_configured = True  # type: ignore[attr-defined]


def current_request_id() -> str:
    """Return the current request correlation ID for response headers."""
    return _request_id.get()


def set_request_id(value: str | None = None) -> contextvars.Token[str]:
    """Set a validated correlation ID for the current async request context."""
    candidate = value or uuid.uuid4().hex
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", candidate):
        candidate = uuid.uuid4().hex
    return _request_id.set(candidate)


def reset_request_id(token: contextvars.Token[str]) -> None:
    """Restore the previous request correlation context."""
    _request_id.reset(token)
