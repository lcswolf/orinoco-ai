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


def test_login_rate_limit_retry_after_reflects_oldest_failure(monkeypatch) -> None:
    """The response delay should match the remaining lockout window, not always 15 minutes."""
    from collections import OrderedDict, deque
    import time

    from fastapi import HTTPException
    from orinoco.auth import routes as auth_routes

    now = time.monotonic()
    monkeypatch.setattr(auth_routes, "_login_failures", OrderedDict({"locked-user": deque([now - 890] * 5)}))
    monkeypatch.setattr(auth_routes.time, "monotonic", lambda: now)

    try:
        auth_routes._check_login_rate("locked-user")
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
        assert second.get("/api/chat/conversations").status_code == 401


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
