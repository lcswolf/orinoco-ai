"""Privacy-conscious structured logging for Orinoco.

Only operational metadata is emitted. Callers must never pass prompts, chat
content, memory values, document text, credentials or request headers.
"""
from __future__ import annotations

import contextvars
import json
import logging
import re
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("orinoco_request_id", default="-")

_SECRET_PATTERNS = (
    re.compile(r"(?i)(bearer\\s+)[A-Za-z0-9._~+/-]+=*"),
    re.compile(r"(?i)((?:password|passwd|token|secret|api[_-]?key|backup[_-]?key|authorization|cookie)\\s*[=:]\\s*)[^\\s,;]+"),
    re.compile(r"(?i)(https?://)[^/@\\s]+:[^/@\\s]+@"),
)


def redact_text(value: str) -> str:
    """Redact common credential forms from operational messages and tracebacks."""
    redacted = value
    for pattern in _SECRET_PATTERNS:
        if pattern.pattern.startswith("(?i)(https"):
            redacted = pattern.sub(r"\\1[REDACTED]@", redacted)
        else:
            redacted = pattern.sub(r"\\1[REDACTED]", redacted)
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


def set_request_id(value: str | None = None) -> contextvars.Token[str]:
    """Set a validated correlation ID for the current async request context."""
    candidate = value or uuid.uuid4().hex
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", candidate):
        candidate = uuid.uuid4().hex
    return _request_id.set(candidate)


def reset_request_id(token: contextvars.Token[str]) -> None:
    """Restore the previous request correlation context."""
    _request_id.reset(token)


def configure_logging() -> None:
    """Configure stdout JSON logs for the Pterodactyl Console."""
    root = logging.getLogger()
    if getattr(root, "_orinoco_logging_configured", False):
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactingFilter())
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    root._orinoco_logging_configured = True  # type: ignore[attr-defined]
