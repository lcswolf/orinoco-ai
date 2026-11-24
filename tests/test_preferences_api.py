"""API tests for private response preferences and administrator persona controls."""

from fastapi.testclient import TestClient

from orinoco.db import create_user, initialise_database
from orinoco.main import app


def _sign_in(client: TestClient, username: str, password: str) -> str:
    """Sign in and return the session-bound CSRF token."""
    token = client.get("/api/auth/csrf").json()["csrf_token"]
    response = client.post(
        "/api/auth/login",
        headers={"X-CSRF-Token": token},
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return client.get("/api/auth/csrf").json()["csrf_token"]


def test_preferences_api_is_authenticated_csrf_protected_and_per_user(tmp_path, monkeypatch) -> None:
    """Changing one account's response preferences must not change another account."""
    database = tmp_path / "preferences-api.sqlite3"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    initialise_database(database)
    create_user("preferenceone", "a-long-test-password-123", database_path=database)
    create_user("preferencetwo", "another-long-password-456", database_path=database)

    with TestClient(app, base_url="https://testserver") as first:
        assert first.get("/api/preferences").status_code == 401
        token = _sign_in(first, "preferenceone", "a-long-test-password-123")
        defaults = first.get("/api/preferences")
        denied = first.put(
            "/api/preferences",
            json={"voice": "calm", "tone": "direct", "answer_detail": "detailed"},
        )
        saved = first.put(
            "/api/preferences",
            headers={"X-CSRF-Token": token},
            json={"voice": "calm", "tone": "direct", "answer_detail": "detailed", "auto_save_memories": False},
        )

    with TestClient(app, base_url="https://testserver") as second:
        _sign_in(second, "preferencetwo", "another-long-password-456")
        other_defaults = second.get("/api/preferences")

    assert defaults.json() == {"voice": "bright", "tone": "friendly", "answer_detail": "balanced", "auto_save_memories": True}
    assert denied.status_code == 403
    assert saved.status_code == 200
    assert saved.json() == {"voice": "calm", "tone": "direct", "answer_detail": "detailed", "auto_save_memories": False}
    assert other_defaults.json() == {"voice": "bright", "tone": "friendly", "answer_detail": "balanced", "auto_save_memories": True}


def test_admin_persona_api_is_admin_only_and_csrf_protected(tmp_path, monkeypatch) -> None:
    """Only an administrator can change the shared core persona and humour setting."""
    database = tmp_path / "admin-persona-api.sqlite3"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    initialise_database(database)
    create_user("standarduser", "a-long-test-password-123", database_path=database)
    create_user("personaadmin", "another-long-password-456", role="admin", database_path=database)

    with TestClient(app, base_url="https://testserver") as standard:
        _sign_in(standard, "standarduser", "a-long-test-password-123")
        forbidden = standard.get("/api/admin/persona")

    with TestClient(app, base_url="https://testserver") as admin:
        token = _sign_in(admin, "personaadmin", "another-long-password-456")
        defaults = admin.get("/api/admin/persona")
        denied = admin.put(
            "/api/admin/persona",
            json={"core_persona": "Be practical and calm.", "humour_level": 25},
        )
        saved = admin.put(
            "/api/admin/persona",
            headers={"X-CSRF-Token": token},
            json={"core_persona": "Be practical and calm.", "humour_level": 25},
        )

    assert forbidden.status_code == 403
    assert defaults.json()["humour_level"] == 65
    assert denied.status_code == 403
    assert saved.status_code == 200
    assert saved.json() == {"core_persona": "Be practical and calm.", "humour_level": 25}
