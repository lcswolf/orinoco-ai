from __future__ import annotations

import json
import sqlite3
import zipfile

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



def test_support_bundle_excludes_free_form_log_messages_and_is_a_valid_zip(tmp_path, monkeypatch):
    database = tmp_path / "data" / "orinoco.sqlite3"
    log_dir = database.parent / "logs"
    log_dir.mkdir(parents=True)
    (log_dir / "orinoco.log").write_text(
        json.dumps({
            "timestamp": "2026-11-26T12:00:00+00:00",
            "level": "ERROR",
            "logger": "orinoco.test",
            "event_code": "test.failure",
            "request_id": "abc123",
            "message": "PRIVATE_CHAT_MESSAGE_DO_NOT_EXPORT",
            "exception": "password=super-secret",
        }) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(diagnostics, "get_database_path", lambda: database)

    async def fake_report():
        return {"status": "pass", "version": "test", "checks": []}

    monkeypatch.setattr(diagnostics, "run_diagnostics", fake_report)
    bundle = anyio.run(diagnostics.build_support_bundle)

    archive_path = tmp_path / "support.zip"
    archive_path.write_bytes(bundle)
    with zipfile.ZipFile(archive_path) as archive:
        assert set(archive.namelist()) == {
            "diagnostics.json", "logs/recent-events.jsonl", "manifest.json"
        }
        exported = "\n".join(archive.read(name).decode("utf-8") for name in archive.namelist())
        assert "test.failure" in exported
        assert "PRIVATE_CHAT_MESSAGE_DO_NOT_EXPORT" not in exported
        assert "super-secret" not in exported
        assert "exception" not in archive.read("logs/recent-events.jsonl").decode("utf-8")



def test_support_bundle_restricts_all_exported_log_metadata(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "orinoco.log"
    log_file.write_text(
        json.dumps({
            "event_code": "valid.event",
            "level": "ERROR",
            "logger": "orinoco.test",
            "request_id": "safe_id-123",
            "timestamp": "2026-11-26T12:00:00+00:00",
            "message": "must never be copied",
        }) + "\n" + json.dumps({
            "event_code": "bad\nevent",
            "level": "ERROR\nINJECTED",
            "logger": "attacker\nforged",
            "request_id": "id\nforged",
            "timestamp": "2026-11-26T12:00:00\nforged",
        }) + "\n",
        encoding="utf-8",
    )

    exported, _ = diagnostics._safe_recent_log_events(log_file)
    records = [json.loads(line) for line in exported.splitlines()]

    assert records == [{
        "event_code": "valid.event",
        "level": "ERROR",
        "logger": "orinoco.test",
        "request_id": "safe_id-123",
        "timestamp": "2026-11-26T12:00:00+00:00",
    }]
    assert "must never be copied" not in exported
    assert "forged" not in exported


def test_support_log_export_refuses_symlink_file_and_directory(tmp_path):
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    real_log = real_dir / "orinoco.log"
    real_log.write_text(json.dumps({"event_code": "safe.event"}) + "\n", encoding="utf-8")

    linked_file = real_dir / "linked.log"
    linked_file.symlink_to(real_log)
    assert diagnostics._safe_recent_log_events(linked_file) == ("", False)

    linked_dir = tmp_path / "linked-dir"
    linked_dir.symlink_to(real_dir, target_is_directory=True)
    assert diagnostics._safe_recent_log_events(linked_dir / "orinoco.log") == ("", False)


def test_support_log_export_rejects_unbounded_limits(tmp_path):
    log_file = tmp_path / "orinoco.log"
    log_file.write_text("", encoding="utf-8")

    with pytest.raises(ValueError):
        diagnostics._safe_recent_log_events(log_file, limit_bytes=2 * 1024 * 1024)
