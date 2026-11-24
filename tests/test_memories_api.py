"""Tests for private per-user memory management."""

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


def test_user_can_create_edit_list_and_delete_own_memory(tmp_path, monkeypatch) -> None:
    database = tmp_path / "orinoco.sqlite3"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    initialise_database(database)
    create_user("memoryuser", "a-long-test-password-123", database_path=database)

    with TestClient(app, base_url="https://testserver") as client:
        sign_in(client, "memoryuser", "a-long-test-password-123")
        headers = {"X-CSRF-Token": csrf(client)}
        created = client.post("/api/memories", headers=headers, json={"content": "  Likes   tea "})
        assert created.status_code == 201
        memory_id = created.json()["memory"]["id"]
        assert created.json()["memory"]["content"] == "Likes tea"

        listing = client.get("/api/memories")
        assert [item["id"] for item in listing.json()["memories"]] == [memory_id]

        edited = client.patch(
            f"/api/memories/{memory_id}",
            headers=headers,
            json={"content": "Prefers green tea"},
        )
        assert edited.status_code == 200
        assert client.get("/api/memories").json()["memories"][0]["content"] == "Prefers green tea"

        deleted = client.delete(f"/api/memories/{memory_id}", headers=headers)
        assert deleted.status_code == 200
        assert client.get("/api/memories").json()["memories"] == []


def test_memories_are_private_between_users(tmp_path, monkeypatch) -> None:
    database = tmp_path / "orinoco.sqlite3"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    initialise_database(database)
    first = create_user("firstmem", "a-long-test-password-123", database_path=database)
    create_user("secondmem", "another-long-password-456", database_path=database)

    with TestClient(app, base_url="https://testserver") as client:
        sign_in(client, "firstmem", "a-long-test-password-123")
        created = client.post(
            "/api/memories",
            headers={"X-CSRF-Token": csrf(client)},
            json={"content": "This is private"},
        )
        memory_id = created.json()["memory"]["id"]
        client.post(
            "/api/auth/logout",
            headers={"X-CSRF-Token": csrf(client)},
        )
        sign_in(client, "secondmem", "another-long-password-456")
        assert client.get("/api/memories").json()["memories"] == []
        response = client.delete(
            f"/api/memories/{memory_id}",
            headers={"X-CSRF-Token": csrf(client)},
        )
        assert response.status_code == 404


def test_memory_api_requires_authentication_and_csrf(tmp_path, monkeypatch) -> None:
    database = tmp_path / "orinoco.sqlite3"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    initialise_database(database)

    with TestClient(app, base_url="https://testserver") as client:
        assert client.get("/api/memories").status_code == 401
        create_user("memoryuser", "a-long-test-password-123", database_path=database)
        sign_in(client, "memoryuser", "a-long-test-password-123")
        response = client.post("/api/memories", json={"content": "No CSRF"})
        assert response.status_code == 403
