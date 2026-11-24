"""Tests for the configured SearXNG client and search route."""

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from orinoco.db import create_user, initialise_database
from orinoco.main import app
from orinoco.research.searxng import SearchUnavailable, SearXNGClient


def test_searxng_client_normalises_and_filters_results(monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_WEB_SEARCH", "true")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/search"
        assert request.url.params["format"] == "json"
        return httpx.Response(
            200,
            json={
                "results": [
                    {"title": "  Useful   result ", "url": "https://example.com/a", "content": "  A   summary  "},
                    {"title": "Unsafe", "url": "javascript:alert(1)", "content": "ignored"},
                    {"title": "Credentials", "url": "https://user:pass@example.com", "content": "ignored"},
                ]
            },
        )

    async def run() -> list[dict[str, str]]:
        client = SearXNGClient(
            base_url="http://searxng.internal",
            transport=httpx.MockTransport(handler),
        )
        try:
            return await client.search("  Orinoco   project ")
        finally:
            await client.aclose()

    results = asyncio.run(run())

    assert results == [
        {
            "title": "Useful result",
            "url": "https://example.com/a",
            "content": "A summary",
            "engine": "SearXNG",
        }
    ]


def test_searxng_requires_configuration_and_admin_enablement(monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_WEB_SEARCH", "false")
    with pytest.raises(SearchUnavailable, match="disabled"):
        SearXNGClient(base_url="https://search.example")

    monkeypatch.setenv("ENABLE_WEB_SEARCH", "true")
    with pytest.raises(SearchUnavailable, match="not been configured"):
        SearXNGClient(base_url="")


def test_search_route_requires_authentication_and_configured_service(tmp_path, monkeypatch) -> None:
    database = tmp_path / "orinoco.sqlite3"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    monkeypatch.setenv("ENABLE_WEB_SEARCH", "false")
    initialise_database(database)
    create_user("researcher", "a-long-test-password-123", database_path=database)

    with TestClient(app, base_url="https://testserver") as client:
        unauthenticated = client.get("/api/research/search?q=Orinoco")
        csrf = client.get("/api/auth/csrf").json()["csrf_token"]
        client.post(
            "/api/auth/login",
            headers={"X-CSRF-Token": csrf},
            json={"username": "researcher", "password": "a-long-test-password-123"},
        )
        disabled = client.get("/api/research/search?q=Orinoco")

    assert unauthenticated.status_code == 401
    assert disabled.status_code == 503
