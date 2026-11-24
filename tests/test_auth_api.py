"""Tests for Orinoco's CSRF-protected authentication API."""

from fastapi.testclient import TestClient

from orinoco.db import create_user, initialise_database
from orinoco.main import app


def test_login_me_and_logout_flow(tmp_path, monkeypatch) -> None:
    database = tmp_path / "accounts.sqlite3"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    initialise_database(database)
    create_user(
        "nugget",
        "a-long-test-password-123",
        role="admin",
        database_path=database,
    )

    with TestClient(app, base_url="https://testserver") as client:
        csrf = client.get("/api/auth/csrf").json()["csrf_token"]
        login = client.post(
            "/api/auth/login",
            headers={"X-CSRF-Token": csrf},
            json={"username": "nugget", "password": "a-long-test-password-123"},
        )

        assert login.status_code == 200
        assert login.json()["authenticated"] is True
        assert login.json()["user"]["role"] == "admin"
        cookie = login.headers.get("set-cookie", "").lower()
        assert "orinoco_session=" in cookie
        assert "httponly" in cookie
        assert "secure" in cookie
        assert "samesite=lax" in cookie
        assert client.get("/api/auth/me").json()["authenticated"] is True

        new_csrf = client.get("/api/auth/csrf").json()["csrf_token"]
        logout = client.post("/api/auth/logout", headers={"X-CSRF-Token": new_csrf})

        assert logout.status_code == 200
        assert client.get("/api/auth/me").json()["authenticated"] is False


def test_login_requires_csrf_token(tmp_path, monkeypatch) -> None:
    database = tmp_path / "accounts.sqlite3"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    initialise_database(database)

    with TestClient(app, base_url="https://testserver") as client:
        response = client.post(
            "/api/auth/login",
            json={"username": "nugget", "password": "a-long-test-password-123"},
        )

    assert response.status_code == 403


def test_login_rejects_incorrect_password(tmp_path, monkeypatch) -> None:
    database = tmp_path / "accounts.sqlite3"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    initialise_database(database)
    create_user("nugget", "a-long-test-password-123", database_path=database)

    with TestClient(app, base_url="https://testserver") as client:
        csrf = client.get("/api/auth/csrf").json()["csrf_token"]
        response = client.post(
            "/api/auth/login",
            headers={"X-CSRF-Token": csrf},
            json={"username": "nugget", "password": "wrong-password"},
        )

    assert response.status_code == 401



def test_login_throttles_repeated_failures(tmp_path, monkeypatch) -> None:
    database = tmp_path / "accounts.sqlite3"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    initialise_database(database)

    with TestClient(app, base_url="https://testserver") as client:
        csrf = client.get("/api/auth/csrf").json()["csrf_token"]
        responses = [
            client.post(
                "/api/auth/login",
                headers={"X-CSRF-Token": csrf},
                json={"username": "rateuser", "password": "incorrect-password"},
            )
            for _ in range(6)
        ]

    assert [response.status_code for response in responses[:5]] == [401] * 5
    assert responses[5].status_code == 429


def test_login_failure_tracker_has_a_hard_memory_bound(monkeypatch) -> None:
    """Rotating usernames must not grow the in-process throttle without limit."""
    from collections import OrderedDict
    import time

    from orinoco.auth import routes as auth_routes

    monkeypatch.setattr(auth_routes, "_login_failures", OrderedDict())
    monkeypatch.setattr(auth_routes, "MAX_TRACKED_LOGIN_IDENTITIES", 2)
    for username in ("first-user", "second-user", "third-user"):
        auth_routes._login_failures_for(username).append(time.monotonic())

    assert len(auth_routes._login_failures) == 2
    assert "first-user" not in auth_routes._login_failures


def test_username_login_throttle_is_scoped_to_client_address(monkeypatch) -> None:
    """Bad attempts from one client must not lock the same account for everyone else."""
    from collections import OrderedDict
    from fastapi import HTTPException
    import time

    from orinoco.auth import routes as auth_routes

    monkeypatch.setattr(auth_routes, "_login_failures", OrderedDict())
    monkeypatch.setattr(auth_routes, "_login_ip_failures", OrderedDict())
    identity = auth_routes._login_identity_key("victim", "192.0.2.10")
    auth_routes._login_failures_for(identity).extend([time.monotonic()] * 5)

    # Another client can still attempt a legitimate sign-in for this account.
    auth_routes._check_login_rate("victim", "192.0.2.11")

    # The original client remains throttled for this username/client pair.
    try:
        auth_routes._check_login_rate("victim", "192.0.2.10")
    except HTTPException as exc:
        assert exc.status_code == 429
    else:
        raise AssertionError("expected the original client to remain rate limited")


def test_login_rate_limit_retry_after_reflects_oldest_failure(monkeypatch) -> None:
    """The response delay should match the remaining lockout window, not always 15 minutes."""
    from collections import OrderedDict, deque
    import time

    from fastapi import HTTPException
    from orinoco.auth import routes as auth_routes

    now = time.monotonic()
    identity = auth_routes._login_identity_key("locked-user", "192.0.2.10")
    monkeypatch.setattr(auth_routes, "_login_failures", OrderedDict({identity: deque([now - 890] * 5)}))
    monkeypatch.setattr(auth_routes.time, "monotonic", lambda: now)

    try:
        auth_routes._check_login_rate("locked-user", "192.0.2.10")
    except HTTPException as exc:
        assert exc.status_code == 429
        assert exc.headers["Retry-After"] == "10"
    else:
        raise AssertionError("expected rate limit response")


def test_password_change_revokes_other_signed_in_sessions(tmp_path, monkeypatch) -> None:
    """Changing a password invalidates every other browser session for that account."""
    database = tmp_path / "accounts.sqlite3"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    initialise_database(database)
    create_user("sessionuser", "a-long-test-password-123", database_path=database)

    with TestClient(app, base_url="https://testserver") as first, TestClient(app, base_url="https://testserver") as second:
        for client in (first, second):
            token = client.get("/api/auth/csrf").json()["csrf_token"]
            response = client.post(
                "/api/auth/login",
                headers={"X-CSRF-Token": token},
                json={"username": "sessionuser", "password": "a-long-test-password-123"},
            )
            assert response.status_code == 200

        token = first.get("/api/auth/csrf").json()["csrf_token"]
        changed = first.post(
            "/api/auth/password",
            headers={"X-CSRF-Token": token},
            json={
                "current_password": "a-long-test-password-123",
                "new_password": "another-long-password-456",
            },
        )

        assert changed.status_code == 200
        assert first.get("/api/auth/me").json()["authenticated"] is True
        assert second.get("/api/auth/me").json()["authenticated"] is False
        assert second.get("/api/conversations").status_code == 401


def test_suspend_and_reactivate_does_not_revive_old_session(tmp_path, monkeypatch) -> None:
    """An account's pre-suspension cookie stays revoked after reactivation."""
    database = tmp_path / "accounts.sqlite3"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    initialise_database(database)
    create_user("adminuser", "a-long-admin-password-123", role="admin", database_path=database)
    target = create_user("targetuser", "a-long-user-password-123", database_path=database)

    with TestClient(app, base_url="https://testserver") as admin, TestClient(app, base_url="https://testserver") as user:
        for client, username, password in (
            (admin, "adminuser", "a-long-admin-password-123"),
            (user, "targetuser", "a-long-user-password-123"),
        ):
            token = client.get("/api/auth/csrf").json()["csrf_token"]
            assert client.post(
                "/api/auth/login",
                headers={"X-CSRF-Token": token},
                json={"username": username, "password": password},
            ).status_code == 200

        admin_token = admin.get("/api/auth/csrf").json()["csrf_token"]
        suspended = admin.patch(
            f"/api/admin/users/{target.id}",
            headers={"X-CSRF-Token": admin_token},
            json={"active": False},
        )
        assert suspended.status_code == 200
        assert user.get("/api/auth/me").json()["authenticated"] is False

        reactivated = admin.patch(
            f"/api/admin/users/{target.id}",
            headers={"X-CSRF-Token": admin_token},
            json={"active": True},
        )
        assert reactivated.status_code == 200
        assert user.get("/api/auth/me").json()["authenticated"] is False

        new_token = user.get("/api/auth/csrf").json()["csrf_token"]
        new_login = user.post(
            "/api/auth/login",
            headers={"X-CSRF-Token": new_token},
            json={"username": "targetuser", "password": "a-long-user-password-123"},
        )
        assert new_login.status_code == 200


def test_session_secret_rejects_symbolic_link(tmp_path, monkeypatch) -> None:
    """A configured session-secret path must never redirect reads outside private storage."""
    import pytest

    from orinoco.auth.sessions import get_session_secret

    target = tmp_path / "external-secret.txt"
    target.write_text("external-secret-value-long-enough-to-pass-validation", encoding="utf-8")
    link = tmp_path / "data" / ".session_secret"
    link.parent.mkdir()
    link.symlink_to(target)
    monkeypatch.delenv("ORINOCO_SECRET_KEY", raising=False)
    monkeypatch.setenv("ORINOCO_SESSION_SECRET_PATH", str(link))

    with pytest.raises(RuntimeError, match="must not be a symbolic link"):
        get_session_secret()


def test_existing_session_secret_permissions_are_restricted(tmp_path, monkeypatch) -> None:
    """Loading a persistent signing secret repairs permissive file mode bits."""
    import os

    from orinoco.auth.sessions import get_session_secret

    secret = tmp_path / "data" / ".session_secret"
    secret.parent.mkdir()
    secret.write_text("existing-session-secret-value-long-enough", encoding="utf-8")
    secret.chmod(0o644)
    monkeypatch.delenv("ORINOCO_SECRET_KEY", raising=False)
    monkeypatch.setenv("ORINOCO_SESSION_SECRET_PATH", str(secret))

    assert get_session_secret() == "existing-session-secret-value-long-enough"
    assert os.stat(secret).st_mode & 0o777 == 0o600


def test_login_throttles_many_distinct_usernames_from_one_client_ip(tmp_path, monkeypatch) -> None:
    """An attacker cannot bypass login throttling simply by rotating usernames."""
    from collections import OrderedDict

    from orinoco.auth import routes as auth_routes

    database = tmp_path / "ip-throttle.sqlite3"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    initialise_database(database)
    monkeypatch.setattr(auth_routes, "_login_failures", OrderedDict())
    monkeypatch.setattr(auth_routes, "_login_ip_failures", OrderedDict())
    monkeypatch.setattr(auth_routes, "MAX_LOGIN_FAILURES_PER_IP", 2)

    with TestClient(app, base_url="https://testserver") as client:
        csrf = client.get("/api/auth/csrf").json()["csrf_token"]
        first = client.post(
            "/api/auth/login",
            headers={"X-CSRF-Token": csrf},
            json={"username": "unknown-one", "password": "incorrect-password"},
        )
        second = client.post(
            "/api/auth/login",
            headers={"X-CSRF-Token": csrf},
            json={"username": "unknown-two", "password": "incorrect-password"},
        )
        third = client.post(
            "/api/auth/login",
            headers={"X-CSRF-Token": csrf},
            json={"username": "unknown-three", "password": "incorrect-password"},
        )

    assert first.status_code == 401
    assert second.status_code == 401
    assert third.status_code == 429


def test_login_ip_failure_tracker_has_a_hard_memory_bound(monkeypatch) -> None:
    """Rotating client addresses must not grow the IP throttle without limit."""
    from collections import OrderedDict
    import time

    from orinoco.auth import routes as auth_routes

    monkeypatch.setattr(auth_routes, "_login_ip_failures", OrderedDict())
    monkeypatch.setattr(auth_routes, "MAX_TRACKED_LOGIN_IDENTITIES", 2)
    for remote_ip in ("192.0.2.1", "192.0.2.2", "192.0.2.3"):
        auth_routes._login_ip_failures_for(remote_ip).append(time.monotonic())

    assert len(auth_routes._login_ip_failures) == 2
    assert "192.0.2.1" not in auth_routes._login_ip_failures


def _request_with_peer(peer: str, forwarded_for: str | None = None):
    """Build a minimal Starlette request with an explicit proxy peer and header."""
    from starlette.requests import Request

    headers = []
    if forwarded_for is not None:
        headers.append((b"x-forwarded-for", forwarded_for.encode("ascii")))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": headers,
        "client": (peer, 12345),
        "server": ("testserver", 80),
    }
    return Request(scope)


def test_production_does_not_treat_shared_proxy_as_client_without_allowlist(monkeypatch) -> None:
    """Until the real proxy peer is measured, avoid a shared username lockout bucket."""
    from orinoco.auth import routes as auth_routes

    monkeypatch.setenv("ORINOCO_ENV", "production")
    monkeypatch.delenv("ORINOCO_TRUSTED_PROXY_IPS", raising=False)
    request = _request_with_peer("127.0.0.1", "8.8.8.8")

    assert auth_routes._resolve_client_ip(request) is None


def test_login_uses_forwarded_ip_only_from_an_allowlisted_proxy(monkeypatch) -> None:
    """A trusted Nginx peer may supply one overwritten client address."""
    from orinoco.auth import routes as auth_routes

    monkeypatch.setenv("ORINOCO_ENV", "production")
    monkeypatch.setenv("ORINOCO_TRUSTED_PROXY_IPS", "127.0.0.1")
    request = _request_with_peer("127.0.0.1", "8.8.8.8")

    assert auth_routes._resolve_client_ip(request) == "8.8.8.8"


def test_login_ignores_forwarded_header_from_untrusted_peer(monkeypatch) -> None:
    """A caller cannot spoof its identity with an untrusted forwarding header."""
    from orinoco.auth import routes as auth_routes

    monkeypatch.setenv("ORINOCO_ENV", "production")
    monkeypatch.setenv("ORINOCO_TRUSTED_PROXY_IPS", "127.0.0.1")
    request = _request_with_peer("8.8.4.4", "1.1.1.1")

    assert auth_routes._resolve_client_ip(request) == "8.8.4.4"


def test_login_rejects_forwarded_header_chains_from_trusted_proxy(monkeypatch) -> None:
    """Only the single client address overwritten by Nginx is accepted."""
    from orinoco.auth import routes as auth_routes

    monkeypatch.setenv("ORINOCO_ENV", "production")
    monkeypatch.setenv("ORINOCO_TRUSTED_PROXY_IPS", "127.0.0.1")
    request = _request_with_peer("127.0.0.1", "8.8.8.8, 1.1.1.1")

    assert auth_routes._resolve_client_ip(request) is None


def test_login_proxy_allowlist_rejects_overly_broad_networks(monkeypatch) -> None:
    """A wildcard-like proxy range must never authorise arbitrary forwarded headers."""
    from orinoco.auth import routes as auth_routes

    monkeypatch.setenv("ORINOCO_ENV", "production")
    monkeypatch.setenv("ORINOCO_TRUSTED_PROXY_IPS", "0.0.0.0/0,::/0")
    request = _request_with_peer("127.0.0.1", "8.8.8.8")

    assert auth_routes._resolve_client_ip(request) is None
