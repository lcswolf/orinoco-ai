"""Tests for private memory CRUD and user isolation."""

from fastapi.testclient import TestClient

from orinoco.db import create_user, initialise_database
from orinoco.memory.store import add_memory
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


def test_user_can_create_review_edit_and_delete_memory(tmp_path, monkeypatch) -> None:
    database = tmp_path / "orinoco.sqlite3"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    initialise_database(database)
    create_user("nugget", "a-long-test-password-123", database_path=database)

    with TestClient(app, base_url="https://testserver") as client:
        sign_in(client, "nugget", "a-long-test-password-123")
        headers = {"X-CSRF-Token": csrf(client)}
        created = client.post("/api/memories", headers=headers, json={"content": "  I prefer concise answers.  "})
        assert created.status_code == 201
        memory_id = created.json()["id"]
        assert created.json()["content"] == "I prefer concise answers."

        listing = client.get("/api/memories").json()["memories"]
        assert len(listing) == 1
        assert listing[0]["content"] == "I prefer concise answers."

        edited = client.patch(
            f"/api/memories/{memory_id}",
            headers=headers,
            json={"content": "I prefer balanced, practical answers."},
        )
        assert edited.status_code == 200
        assert client.get("/api/memories").json()["memories"][0]["content"] == "I prefer balanced, practical answers."

        deleted = client.delete(f"/api/memories/{memory_id}", headers=headers)
        assert deleted.status_code == 200
        assert client.get("/api/memories").json()["memories"] == []


def test_users_cannot_view_or_change_another_users_memories(tmp_path, monkeypatch) -> None:
    database = tmp_path / "orinoco.sqlite3"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    initialise_database(database)
    first = create_user("firstuser", "a-long-first-password-123", database_path=database)
    create_user("seconduser", "a-long-second-password-456", database_path=database)
    memory = add_memory(first.id, "This is private to the first account.")

    with TestClient(app, base_url="https://testserver") as client:
        sign_in(client, "seconduser", "a-long-second-password-456")
        assert client.get("/api/memories").json()["memories"] == []
        edit = client.patch(
            f"/api/memories/{memory['id']}",
            headers={"X-CSRF-Token": csrf(client)},
            json={"content": "Trying to change someone else's memory."},
        )
        delete = client.delete(
            f"/api/memories/{memory['id']}",
            headers={"X-CSRF-Token": csrf(client)},
        )

    assert edit.status_code == 404
    assert delete.status_code == 404


def test_memories_require_sign_in_and_csrf_for_changes(tmp_path, monkeypatch) -> None:
    database = tmp_path / "orinoco.sqlite3"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    initialise_database(database)

    with TestClient(app, base_url="https://testserver") as client:
        assert client.get("/api/memories").status_code == 401
        create_user("nugget", "a-long-test-password-123", database_path=database)
        sign_in(client, "nugget", "a-long-test-password-123")
        response = client.post("/api/memories", json={"content": "This request has no CSRF token."})

    assert response.status_code == 403
