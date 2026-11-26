from __future__ import annotations

import sqlite3

import anyio
import pytest

from orinoco import diagnostics


def test_database_check_uses_read_only_connection_and_reports_schema(tmp_path, monkeypatch):
    path = tmp_path / "orinoco.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA user_version = 17")
    connection.close()
    monkeypatch.setattr(diagnostics, "get_database_path", lambda: path)

    result = diagnostics.check_database()

    assert result["status"] == "pass"
    assert result["schema_version"] == 17


def test_database_check_reports_missing_database_without_creating_it(tmp_path, monkeypatch):
    path = tmp_path / "missing.sqlite3"
    monkeypatch.setattr(diagnostics, "get_database_path", lambda: path)

    result = diagnostics.check_database()

    assert result["status"] == "fail"
    assert not path.exists()


def test_storage_checks_do_not_create_missing_directories(tmp_path, monkeypatch):
    root = tmp_path / "data"
    monkeypatch.setattr(diagnostics, "get_database_path", lambda: root / "orinoco.sqlite3")

    results = diagnostics.check_storage()

    assert results
    assert not root.exists()
    assert all(item["status"] in {"pass", "warning", "fail"} for item in results)


def test_ollama_check_reports_missing_model_without_downloading(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"models": [{"name": "other:1b"}]}

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url):
            assert url.endswith("/api/tags")
            return Response()

    monkeypatch.setattr(diagnostics.httpx, "AsyncClient", Client)
    result = anyio.run(diagnostics.check_ollama, "wanted:1b")

    assert result["status"] == "warning"
    assert result["selected_model"] == "wanted:1b"


def test_ollama_check_reports_unavailable_service(monkeypatch):
    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url):
            raise diagnostics.httpx.ConnectError("not available")

    monkeypatch.setattr(diagnostics.httpx, "AsyncClient", Client)
    result = anyio.run(diagnostics.check_ollama)

    assert result["status"] == "fail"
    assert "could not be reached" in result["summary"]


def test_run_diagnostics_combines_results(monkeypatch):
    monkeypatch.setattr(diagnostics, "check_database", lambda: {"name": "database", "status": "pass", "summary": "ok"})
    monkeypatch.setattr(diagnostics, "check_storage", lambda: [])
    async def ollama():
        return {"name": "ollama", "status": "warning", "summary": "missing model"}
    monkeypatch.setattr(diagnostics, "check_ollama", ollama)

    result = anyio.run(diagnostics.run_diagnostics)

    assert result["status"] == "warning"
    assert [item["name"] for item in result["checks"]] == ["database", "ollama"]
