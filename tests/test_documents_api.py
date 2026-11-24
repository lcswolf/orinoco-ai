"""Tests for private and shared document libraries."""

from fastapi.testclient import TestClient

from orinoco.db import create_user, initialise_database, search_documents
from orinoco.main import app


def csrf(client: TestClient) -> str:
    return client.get("/api/auth/csrf").json()["csrf_token"]


def sign_in(client: TestClient, username: str, password: str) -> None:
    token = csrf(client)
    response = client.post(
        "/api/auth/login",
        headers={"X-CSRF-Token": token},
        json={"username": username, "password": password},
    )
    assert response.status_code == 200


def test_private_document_upload_download_and_delete(tmp_path, monkeypatch) -> None:
    database = tmp_path / "orinoco.sqlite3"
    storage = tmp_path / "documents"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    monkeypatch.setenv("ORINOCO_DOCUMENTS_PATH", str(storage))
    initialise_database(database)
    create_user("docuser", "a-long-test-password-123", database_path=database)

    with TestClient(app, base_url="https://testserver") as client:
        sign_in(client, "docuser", "a-long-test-password-123")
        upload = client.post(
            "/api/documents",
            headers={"X-CSRF-Token": csrf(client)},
            files={"file": ("notes.txt", b"Orinoco private document search phrase.", "text/plain")},
        )
        assert upload.status_code == 201
        document_id = upload.json()["document"]["id"]

        listing = client.get("/api/documents").json()["documents"]
        assert len(listing) == 1
        assert listing[0]["scope"] == "private"

        download = client.get(f"/api/documents/{document_id}/download")
        assert download.status_code == 200
        assert download.content == b"Orinoco private document search phrase."

        deleted = client.delete(
            f"/api/documents/{document_id}",
            headers={"X-CSRF-Token": csrf(client)},
        )
        assert deleted.status_code == 200
        assert client.get("/api/documents").json()["documents"] == []


def test_private_documents_are_isolated_between_users(tmp_path, monkeypatch) -> None:
    database = tmp_path / "orinoco.sqlite3"
    storage = tmp_path / "documents"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    monkeypatch.setenv("ORINOCO_DOCUMENTS_PATH", str(storage))
    initialise_database(database)
    create_user("firstdoc", "a-long-first-password-123", database_path=database)
    create_user("seconddoc", "a-long-second-password-456", database_path=database)

    with TestClient(app, base_url="https://testserver") as client:
        sign_in(client, "firstdoc", "a-long-first-password-123")
        upload = client.post(
            "/api/documents",
            headers={"X-CSRF-Token": csrf(client)},
            files={"file": ("private.txt", b"Only the first user can see this.", "text/plain")},
        )
        document_id = upload.json()["document"]["id"]
        client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf(client)})
        sign_in(client, "seconddoc", "a-long-second-password-456")

        assert client.get("/api/documents").json()["documents"] == []
        download = client.get(f"/api/documents/{document_id}/download")
        deletion = client.delete(
            f"/api/documents/{document_id}",
            headers={"X-CSRF-Token": csrf(client)},
        )

    assert download.status_code == 404
    assert deletion.status_code == 404


def test_admin_shared_document_is_available_to_users_but_only_admin_can_delete(
    tmp_path, monkeypatch
) -> None:
    database = tmp_path / "orinoco.sqlite3"
    storage = tmp_path / "documents"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    monkeypatch.setenv("ORINOCO_DOCUMENTS_PATH", str(storage))
    initialise_database(database)
    create_user("adminuser", "a-long-admin-password-123", role="admin", database_path=database)
    create_user("normaluser", "a-long-user-password-456", database_path=database)

    with TestClient(app, base_url="https://testserver") as client:
        sign_in(client, "adminuser", "a-long-admin-password-123")
        upload = client.post(
            "/api/admin/shared-documents",
            headers={"X-CSRF-Token": csrf(client)},
            files={"file": ("guide.md", b"Shared library installation guide.", "text/markdown")},
        )
        assert upload.status_code == 201
        document_id = upload.json()["document"]["id"]

        client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf(client)})
        sign_in(client, "normaluser", "a-long-user-password-456")
        visible = client.get("/api/documents").json()["documents"]
        assert any(item["id"] == document_id and item["scope"] == "shared" for item in visible)
        denied = client.delete(
            f"/api/documents/{document_id}",
            headers={"X-CSRF-Token": csrf(client)},
        )
        assert denied.status_code == 404

        client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf(client)})
        sign_in(client, "adminuser", "a-long-admin-password-123")
        deleted = client.delete(
            f"/api/admin/shared-documents/{document_id}",
            headers={"X-CSRF-Token": csrf(client)},
        )
        assert deleted.status_code == 200


def test_unsupported_upload_type_is_rejected(tmp_path, monkeypatch) -> None:
    database = tmp_path / "orinoco.sqlite3"
    storage = tmp_path / "documents"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    monkeypatch.setenv("ORINOCO_DOCUMENTS_PATH", str(storage))
    initialise_database(database)
    create_user("docuser", "a-long-test-password-123", database_path=database)

    with TestClient(app, base_url="https://testserver") as client:
        sign_in(client, "docuser", "a-long-test-password-123")
        response = client.post(
            "/api/documents",
            headers={"X-CSRF-Token": csrf(client)},
            files={"file": ("bad.exe", b"not a document", "application/octet-stream")},
        )

    assert response.status_code == 422


def test_document_search_is_scoped_to_owner_and_shared_library(tmp_path) -> None:
    from orinoco.db import create_document

    database = tmp_path / "orinoco.sqlite3"
    initialise_database(database)
    first = create_user("firstdoc", "a-long-first-password-123", database_path=database)
    second = create_user("seconddoc", "a-long-second-password-456", database_path=database)

    create_document(
        owner_user_id=first.id,
        scope="private",
        original_name="private.txt",
        stored_path="private/1/private.txt",
        file_type="txt",
        size_bytes=20,
        sha256="a" * 64,
        extracted_text="The secret phrase belongs to the first user.",
        database_path=database,
    )
    create_document(
        owner_user_id=None,
        scope="shared",
        original_name="shared.txt",
        stored_path="shared/shared.txt",
        file_type="txt",
        size_bytes=20,
        sha256="b" * 64,
        extracted_text="Shared handbook includes the installation phrase.",
        database_path=database,
    )

    assert len(search_documents(first.id, "secret phrase", database_path=database)) == 1
    assert search_documents(second.id, "secret phrase", database_path=database) == []
    assert len(search_documents(second.id, "installation phrase", database_path=database)) == 1


def test_failed_private_file_cleanup_keeps_document_record(tmp_path, monkeypatch) -> None:
    """A failed unlink must not silently remove the only record of private data."""
    from orinoco.documents import routes as document_routes

    database = tmp_path / "orinoco.sqlite3"
    storage = tmp_path / "documents"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    monkeypatch.setenv("ORINOCO_DOCUMENTS_PATH", str(storage))
    initialise_database(database)
    create_user("docuser", "a-long-test-password-123", database_path=database)

    with TestClient(app, base_url="https://testserver") as client:
        sign_in(client, "docuser", "a-long-test-password-123")
        upload = client.post(
            "/api/documents",
            headers={"X-CSRF-Token": csrf(client)},
            files={"file": ("notes.txt", b"Keep this document record if unlink fails.", "text/plain")},
        )
        document_id = upload.json()["document"]["id"]

        def fail_remove(path: str) -> None:
            raise OSError("simulated filesystem permission failure")

        monkeypatch.setattr(document_routes, "remove_document_file", fail_remove)
        deletion = client.delete(
            f"/api/documents/{document_id}",
            headers={"X-CSRF-Token": csrf(client)},
        )
        listing = client.get("/api/documents").json()["documents"]

    assert deletion.status_code == 500
    assert any(item["id"] == document_id for item in listing)
