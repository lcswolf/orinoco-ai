"""Tests for privacy-conscious structured application logging."""

from __future__ import annotations

import json
import logging

from orinoco.logging_config import JsonFormatter, RedactingFilter, redact_text, reset_request_id, set_request_id


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
