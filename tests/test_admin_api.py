"""Tests for administrator account management and password changes."""

from fastapi.testclient import TestClient

from orinoco.db import create_user, initialise_database
from orinoco.main import app


def sign_in(client: TestClient, username: str, password: str) -> None:
    csrf = client.get("/api/auth/csrf").json()["csrf_token"]
    response = client.post(
        "/api/auth/login",
        headers={"X-CSRF-Token": csrf},
        json={"username": username, "password": password},
    )
    assert response.status_code == 200


def csrf(client: TestClient) -> str:
    return client.get("/api/auth/csrf").json()["csrf_token"]


def test_admin_can_create_and_suspend_standard_user(tmp_path, monkeypatch) -> None:
    database = tmp_path / "orinoco.sqlite3"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    initialise_database(database)
    create_user("adminuser", "a-long-admin-password-123", role="admin", database_path=database)

    with TestClient(app, base_url="https://testserver") as client:
        sign_in(client, "adminuser", "a-long-admin-password-123")
        response = client.post(
            "/api/admin/users",
            headers={"X-CSRF-Token": csrf(client)},
            json={"username": "newuser", "password": "a-long-user-password-456"},
        )
        assert response.status_code == 201
        new_user_id = response.json()["user"]["id"]

        listing = client.get("/api/admin/users")
        assert listing.status_code == 200
        assert any(user["username"] == "newuser" for user in listing.json()["users"])

        suspended = client.patch(
            f"/api/admin/users/{new_user_id}",
            headers={"X-CSRF-Token": csrf(client)},
            json={"active": False},
        )
        assert suspended.status_code == 200

    from orinoco.db import authenticate_user

    assert authenticate_user(
        "newuser", "a-long-user-password-456", database_path=database
    ) is None


def test_standard_user_cannot_access_admin_api(tmp_path, monkeypatch) -> None:
    database = tmp_path / "orinoco.sqlite3"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    initialise_database(database)
    create_user("normaluser", "a-long-user-password-456", database_path=database)

    with TestClient(app, base_url="https://testserver") as client:
        sign_in(client, "normaluser", "a-long-user-password-456")
        response = client.get("/api/admin/users")
        diagnostics_response = client.get("/api/admin/diagnostics")
        bundle_response = client.get("/api/admin/diagnostics/support-bundle")

    assert response.status_code == 403
    assert diagnostics_response.status_code == 403
    assert bundle_response.status_code == 403


def test_admin_cannot_suspend_self_or_last_admin(tmp_path, monkeypatch) -> None:
    database = tmp_path / "orinoco.sqlite3"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    initialise_database(database)
    admin = create_user("adminuser", "a-long-admin-password-123", role="admin", database_path=database)

    with TestClient(app, base_url="https://testserver") as client:
        sign_in(client, "adminuser", "a-long-admin-password-123")
        response = client.patch(
            f"/api/admin/users/{admin.id}",
            headers={"X-CSRF-Token": csrf(client)},
            json={"active": False},
        )

    assert response.status_code == 400


def test_user_can_change_password_and_session_is_rotated(tmp_path, monkeypatch) -> None:
    database = tmp_path / "orinoco.sqlite3"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    initialise_database(database)
    create_user("nugget", "a-long-test-password-123", database_path=database)

    with TestClient(app, base_url="https://testserver") as client:
        sign_in(client, "nugget", "a-long-test-password-123")
        response = client.post(
            "/api/auth/password",
            headers={"X-CSRF-Token": csrf(client)},
            json={
                "current_password": "a-long-test-password-123",
                "new_password": "a-new-secure-password-789",
            },
        )
        assert response.status_code == 200
        assert client.get("/api/auth/me").json()["authenticated"] is True

    from orinoco.db import authenticate_user

    assert authenticate_user(
        "nugget", "a-new-secure-password-789", database_path=database
    ) is not None



def test_admin_can_run_diagnostics(tmp_path, monkeypatch) -> None:
    from orinoco import diagnostics

    async def fake_diagnostics():
        return {"status": "pass", "version": "test", "checks": []}

    monkeypatch.setattr(diagnostics, "run_diagnostics", fake_diagnostics)
    database = tmp_path / "orinoco.sqlite3"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    initialise_database(database)
    create_user("adminuser", "a-long-admin-password-123", role="admin", database_path=database)

    with TestClient(app, base_url="https://testserver") as client:
        sign_in(client, "adminuser", "a-long-admin-password-123")
        response = client.get("/api/admin/diagnostics")

    assert response.status_code == 200
    assert response.json() == {"status": "pass", "version": "test", "checks": []}



def test_admin_can_download_support_bundle(tmp_path, monkeypatch) -> None:
    from orinoco import diagnostics

    async def fake_bundle():
        return b"safe-test-zip"

    monkeypatch.setattr(diagnostics, "build_support_bundle", fake_bundle)
    database = tmp_path / "orinoco.sqlite3"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    initialise_database(database)
    create_user("adminuser", "a-long-admin-password-123", role="admin", database_path=database)

    with TestClient(app, base_url="https://testserver") as client:
        sign_in(client, "adminuser", "a-long-admin-password-123")
        response = client.get("/api/admin/diagnostics/support-bundle")

    assert response.status_code == 200
    assert response.content == b"safe-test-zip"
    assert response.headers["content-type"] == "application/zip"
    assert "no-store" in response.headers["cache-control"]
