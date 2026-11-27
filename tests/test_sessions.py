""""Tests for persistent signing-secret configuration."""

from pathlib import Path

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


def test_production_rejects_existing_session_secret_with_unverifiable_permissions(tmp_path, monkeypatch) -> None:
    secret_path = tmp_path / "private" / "session.secret"
    secret_path.parent.mkdir()
    secret_path.write_text("existing-session-secret-value-long-enough", encoding="utf-8")
    secret_path.chmod(0o644)
    monkeypatch.delenv("ORINOCO_SECRET_KEY", raising=False)
    monkeypatch.setenv("ORINOCO_ENV", "production")
    monkeypatch.setenv("ORINOCO_SESSION_SECRET_PATH", str(secret_path))
    original_chmod = Path.chmod

    def fail_secret_chmod(path: Path, mode: int) -> None:
        if path == secret_path:
            raise PermissionError("simulated read-only secret file")
        original_chmod(path, mode)

    monkeypatch.setattr(Path, "chmod", fail_secret_chmod)

    with pytest.raises(RuntimeError, match="not private"):
        get_session_secret()


def test_short_configured_session_secret_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("ORINOCO_SECRET_KEY", "too-short")

    with pytest.raises(RuntimeError, match="at least 32"):
        get_session_secret()


def test_secure_cookies_are_enabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("ORINOCO_COOKIE_SECURE", raising=False)

    assert secure_cookie_enabled() is True
