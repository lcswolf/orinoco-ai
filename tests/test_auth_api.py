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
