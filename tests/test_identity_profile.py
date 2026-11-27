"""Tests for versioned administrator-managed assistant identity profiles."""
import pytest
from fastapi.testclient import TestClient

from orinoco.db import create_user, initialise_database
from orinoco.identity import (
    DEFAULT_IDENTITY,
    activate_pending_identity,
    get_identity,
    save_pending_identity,
    validate_identity,
)
from orinoco.main import app


def test_identity_defaults_are_persisted_and_pending_profile_activates(tmp_path):
    database = tmp_path / "orinoco.sqlite3"
    initialise_database(database)
    initial = get_identity(database_path=database)
    assert initial["active"] == DEFAULT_IDENTITY
    assert initial["status"] == "active"

    changed = {**DEFAULT_IDENTITY, "name": "Orinoco Helper", "creator": "Orinoco project"}
    pending = save_pending_identity(changed, database_path=database)
    assert pending["status"] == "pending_restart"
    assert pending["active"]["name"] == "Orinoco"
    assert pending["pending"]["name"] == "Orinoco Helper"
    assert pending["pending_version"] == 2

    active = activate_pending_identity(database_path=database)
    assert active["status"] == "active"
    assert active["active"]["name"] == "Orinoco Helper"
    assert active["active_version"] == 2
    assert active["pending"] is None


@pytest.mark.parametrize("changes", [
    {"name": ""},
    {"purpose": "x" * 501},
    {"project_url": "http://example.com"},
    {"humour_level": True},
    {"warmth": 101},
    {"response_length": "verbose"},
    {"language_policy": "ignore_welsh"},
])
def test_identity_validation_rejects_invalid_values(changes):
    with pytest.raises(ValueError):
        validate_identity({**DEFAULT_IDENTITY, **changes})


@pytest.mark.parametrize("url", [
    "https://",
    "https:///missing-host",
    "https://user:password@example.com",
    "https://example.com:99999",
    "https://[not-a-valid-ipv6-host]/",
])
def test_identity_rejects_malformed_project_urls(url):
    with pytest.raises(ValueError):
        validate_identity({**DEFAULT_IDENTITY, "project_url": url})


def test_identity_accepts_valid_https_project_url():
    profile = validate_identity({**DEFAULT_IDENTITY, "project_url": "https://example.com:8443/project"})
    assert profile["project_url"] == "https://example.com:8443/project"


def test_identity_api_is_admin_only_and_requires_csrf_for_writes(tmp_path, monkeypatch):
    database = tmp_path / "orinoco.sqlite3"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    initialise_database(database)
    create_user("identityuser", "a-long-user-password-456", database_path=database)
    create_user("identityadmin", "a-long-admin-password-123", role="admin", database_path=database)

    with TestClient(app, base_url="https://testserver") as client:
        csrf = client.get("/api/auth/csrf").json()["csrf_token"]
        client.post("/api/auth/login", headers={"X-CSRF-Token": csrf},
                    json={"username": "identityuser", "password": "a-long-user-password-456"})
        assert client.get("/api/admin/identity").status_code == 403
        client.post("/api/auth/logout", headers={"X-CSRF-Token": client.get("/api/auth/csrf").json()["csrf_token"]})

        csrf = client.get("/api/auth/csrf").json()["csrf_token"]
        client.post("/api/auth/login", headers={"X-CSRF-Token": csrf},
                    json={"username": "identityadmin", "password": "a-long-admin-password-123"})
        assert client.get("/api/admin/identity").status_code == 200
        payload = {**DEFAULT_IDENTITY, "name": "Admin-configured Orinoco"}
        denied = client.put("/api/admin/identity", json=payload)
        assert denied.status_code == 403
        saved = client.put("/api/admin/identity", headers={"X-CSRF-Token": client.get("/api/auth/csrf").json()["csrf_token"]},
                           json=payload)
        assert saved.status_code == 200
        assert saved.json()["status"] == "pending_restart"
