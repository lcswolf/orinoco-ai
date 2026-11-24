"""Tests for persistent signing-secret configuration."""

import pytest

from orinoco.auth.sessions import get_session_secret, secure_cookie_enabled


def test_session_secret_is_created_persistently_with_private_permissions(tmp_path, monkeypatch) -> None:
    secret_path = tmp_path / "private" / "session.secret"
    monkeypatch.delenv("ORINOCO_SECRET_KEY", raising=False)
    monkeypatch.setenv("ORINOCO_SESSION_SECRET_PATH", str(secret_path))

    first = get_session_secret()
    second = get_session_secret()

    assert len(first) >= 32
    assert second == first
    assert secret_path.stat().st_mode & 0o777 == 0o600


def test_short_configured_session_secret_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("ORINOCO_SECRET_KEY", "too-short")

    with pytest.raises(RuntimeError, match="at least 32"):
        get_session_secret()


def test_secure_cookies_are_enabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("ORINOCO_COOKIE_SECURE", raising=False)

    assert secure_cookie_enabled() is True
