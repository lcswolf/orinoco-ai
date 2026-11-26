"""Tests for privacy-conscious structured application logging."""

from __future__ import annotations

import json
import logging
import os
import stat

import pytest

from orinoco.logging_config import (
    JsonFormatter,
    PrivateRotatingFileHandler,
    RedactingFilter,
    redact_text,
    reset_request_id,
    set_request_id,
)


def test_redact_text_removes_common_credentials() -> None:
    message = (
        "Authorization: Bearer abc.def.ghi password=hunter2 "
        "backup_key=verysecret https://user:pass@example.test/path"
    )
    cleaned = redact_text(message)
    assert "abc.def.ghi" not in cleaned
    assert "hunter2" not in cleaned
    assert "verysecret" not in cleaned
    assert "user:pass" not in cleaned
    assert "[REDACTED]" in cleaned


def test_json_log_has_timestamp_level_and_correlation_id() -> None:
    token = set_request_id("request_12345678")
    try:
        record = logging.LogRecord("orinoco.test", logging.ERROR, __file__, 12, "operation failed", (), None)
        RedactingFilter().filter(record)
        payload = json.loads(JsonFormatter().format(record))
    finally:
        reset_request_id(token)

    assert payload["level"] == "ERROR"
    assert payload["request_id"] == "request_12345678"
    assert payload["message"] == "operation failed"
    assert payload["timestamp"].endswith("+00:00")


def test_invalid_incoming_correlation_id_is_replaced() -> None:
    token = set_request_id("bad id with spaces")
    try:
        record = logging.LogRecord("orinoco.test", logging.INFO, __file__, 1, "ok", (), None)
        RedactingFilter().filter(record)
        assert len(record.request_id) == 32
        assert " " not in record.request_id
    finally:
        reset_request_id(token)


def test_filter_redacts_formatted_message_arguments() -> None:
    record = logging.LogRecord("orinoco.test", logging.WARNING, __file__, 1, "token=%s", ("secret-value",), None)
    RedactingFilter().filter(record)
    assert "secret-value" not in record.getMessage()


def test_filter_redacts_exception_text_populated_by_another_handler() -> None:
    record = logging.LogRecord("orinoco.test", logging.ERROR, __file__, 1, "operation failed", (), None)
    record.exc_text = "RuntimeError: token=already-formatted-secret"
    RedactingFilter().filter(record)
    payload = json.loads(JsonFormatter().format(record))
    assert "already-formatted-secret" not in payload["exception"]
    assert "[REDACTED]" in payload["exception"]


def test_private_rotating_handler_writes_redacted_json_with_private_permissions(tmp_path) -> None:
    path = tmp_path / "orinoco.log"
    handler = PrivateRotatingFileHandler(path, maxBytes=1024, backupCount=2, encoding="utf-8")
    handler.addFilter(RedactingFilter())
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("orinoco.test.file")
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    try:
        logger.error("token=%s", "disk-secret")
        handler.flush()
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert "disk-secret" not in path.read_text(encoding="utf-8")
        assert "[REDACTED]" in payload["message"]
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    finally:
        logger.removeHandler(handler)
        handler.close()
        logger.propagate = True


def test_private_rotating_handler_rotates_with_bounded_backups(tmp_path) -> None:
    path = tmp_path / "orinoco.log"
    handler = PrivateRotatingFileHandler(path, maxBytes=120, backupCount=2, encoding="utf-8")
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("orinoco.test.rotation")
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    try:
        for index in range(20):
            logger.info("diagnostic event %s with a bounded message", index)
        handler.flush()
        assert path.exists()
        assert (tmp_path / "orinoco.log.1").exists()
        assert (tmp_path / "orinoco.log.2").exists()
        assert not (tmp_path / "orinoco.log.3").exists()
    finally:
        logger.removeHandler(handler)
        handler.close()
        logger.propagate = True


def test_private_rotating_handler_refuses_symlink(tmp_path) -> None:
    target = tmp_path / "outside.txt"
    target.write_text("do not overwrite", encoding="utf-8")
    link = tmp_path / "orinoco.log"
    link.symlink_to(target)
    with pytest.raises(OSError):
        PrivateRotatingFileHandler(link, maxBytes=1024, backupCount=1, encoding="utf-8")
    assert target.read_text(encoding="utf-8") == "do not overwrite"


def test_private_rotating_handler_restricts_existing_file_mode(tmp_path) -> None:
    path = tmp_path / "orinoco.log"
    path.write_text("old log", encoding="utf-8")
    os.chmod(path, 0o644)
    handler = PrivateRotatingFileHandler(path, maxBytes=1024, backupCount=1, encoding="utf-8")
    try:
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    finally:
        handler.close()
