"""Tests for SSRF-resistant webpage fetching and local summaries."""

import asyncio
import socket

import pytest
from fastapi.testclient import TestClient

from orinoco.db import create_user, initialise_database
from orinoco.main import app
from orinoco.research import routes as research_routes
from orinoco.research.webpage import (
    FetchedPage,
    PublicResolver,
    SafeFetchError,
    _extract_readable_text,
    validate_url_syntax,
)


def test_url_validation_allows_public_http_and_https_only() -> None:
    assert validate_url_syntax("https://example.com/article") == (
        "https", "example.com", 443
    )
    assert validate_url_syntax("http://example.com:80/page") == (
        "http", "example.com", 80
    )


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/file",
        "http://localhost/",
        "http://127.0.0.1/",
        "http://10.0.0.5/",
        "http://192.168.1.10/",
        "http://service.internal/",
        "https://example.com:8443/",
        "https://user:pass@example.com/",
    ],
)
def test_url_validation_rejects_private_or_unsupported_targets(url: str) -> None:
    with pytest.raises(SafeFetchError):
        validate_url_syntax(url)


def test_public_resolver_rejects_private_dns_results(monkeypatch) -> None:
    class FakeLoop:
        async def getaddrinfo(self, host, port, family, type):
            return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("10.1.2.3", port))]

    monkeypatch.setattr(asyncio, "get_running_loop", lambda: FakeLoop())

    async def run() -> None:
        with pytest.raises(OSError, match="non-public"):
            await PublicResolver().resolve("rebind.example", 443, socket.AF_UNSPEC)

    asyncio.run(run())


def test_html_extraction_removes_scripts_and_navigation() -> None:
    html = b"""
    <html><head><title>Useful article</title><script>steal()</script></head>
    <body><nav>Navigation noise</nav><main><h1>Article heading</h1>
    <p>This is the actual article text with enough readable content.</p></main>
    <footer>Footer noise</footer></body></html>
    """
    title, text = _extract_readable_text(html, "text/html", "utf-8")

    assert title == "Useful article"
    assert "actual article text" in text
    assert "steal()" not in text
    assert "Navigation noise" not in text
    assert "Footer noise" not in text


def test_authenticated_summary_uses_local_model_and_returns_source(tmp_path, monkeypatch) -> None:
    database = tmp_path / "orinoco.sqlite3"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    monkeypatch.setenv("ENABLE_WEB_SEARCH", "true")
    initialise_database(database)
    create_user("webuser", "a-long-test-password-123", database_path=database)

    async def fake_fetch(url: str) -> FetchedPage:
        assert url == "https://example.com/article"
        return FetchedPage(
            url=url,
            title="Example article",
            text="This public article explains how local AI assistants can run privately.",
        )

    class FakeOllamaClient:
        async def chat(self, messages: list[dict[str, str]]) -> str:
            assert "untrusted reference data" in messages[1]["content"]
            return "The article describes private, locally hosted AI assistants."

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(research_routes, "fetch_public_page", fake_fetch)
    monkeypatch.setattr(research_routes, "OllamaClient", FakeOllamaClient)

    with TestClient(app, base_url="https://testserver") as client:
        token = client.get("/api/auth/csrf").json()["csrf_token"]
        client.post(
            "/api/auth/login",
            headers={"X-CSRF-Token": token},
            json={"username": "webuser", "password": "a-long-test-password-123"},
        )
        token = client.get("/api/auth/csrf").json()["csrf_token"]
        response = client.post(
            "/api/research/summarise",
            headers={"X-CSRF-Token": token},
            json={"url": "https://example.com/article"},
        )

    assert response.status_code == 200
    assert response.json()["title"] == "Example article"
    assert response.json()["summary"].startswith("The article describes")


def test_unsafe_webpage_is_rejected_before_model_call(tmp_path, monkeypatch) -> None:
    database = tmp_path / "orinoco.sqlite3"
    monkeypatch.setenv("ORINOCO_DATABASE_PATH", str(database))
    monkeypatch.setenv("ENABLE_WEB_SEARCH", "true")
    initialise_database(database)
    create_user("webuser", "a-long-test-password-123", database_path=database)

    with TestClient(app, base_url="https://testserver") as client:
        token = client.get("/api/auth/csrf").json()["csrf_token"]
        client.post(
            "/api/auth/login",
            headers={"X-CSRF-Token": token},
            json={"username": "webuser", "password": "a-long-test-password-123"},
        )
        token = client.get("/api/auth/csrf").json()["csrf_token"]
        response = client.post(
            "/api/research/summarise",
            headers={"X-CSRF-Token": token},
            json={"url": "http://127.0.0.1/"},
        )

    assert response.status_code == 422


def test_public_fetch_rejects_redirect_to_private_address(monkeypatch) -> None:
    """A safe first URL must not be allowed to redirect into a private network."""
    class FakeResponse:
        status = 302
        headers = {"Location": "http://127.0.0.1/admin"}
        url = "https://example.com/start"

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    class FakeSession:
        calls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        def get(self, *args, **kwargs):
            self.calls += 1
            return FakeResponse()

    fake_session = FakeSession()
    monkeypatch.setattr("orinoco.research.webpage.aiohttp.ClientSession", lambda **kwargs: fake_session)

    async def run() -> None:
        with pytest.raises(SafeFetchError, match="Private and local"):
            await research_routes.fetch_public_page("https://example.com/start")
        assert fake_session.calls == 1

    asyncio.run(run())


def test_public_fetch_stops_after_redirect_limit(monkeypatch) -> None:
    """Redirect loops must stop at the documented maximum without following a fifth hop."""
    class FakeResponse:
        status = 302
        headers = {"Location": "https://example.com/next"}
        url = "https://example.com/next"

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    class FakeSession:
        calls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        def get(self, *args, **kwargs):
            self.calls += 1
            return FakeResponse()

    fake_session = FakeSession()
    monkeypatch.setattr("orinoco.research.webpage.aiohttp.ClientSession", lambda **kwargs: fake_session)

    async def run() -> None:
        with pytest.raises(SafeFetchError, match="redirected too many times"):
            await research_routes.fetch_public_page("https://example.com/start")
        assert fake_session.calls == 4

    asyncio.run(run())


def test_public_fetch_enforces_decompressed_response_size_limit(monkeypatch) -> None:
    """The streamed, decompressed response body must stay within the 2 MiB cap."""
    from types import SimpleNamespace

    from orinoco.research.webpage import MAX_PAGE_BYTES

    class FakeContent:
        async def iter_chunked(self, chunk_size):
            yield b"x" * (MAX_PAGE_BYTES + 1)

    class FakeResponse:
        status = 200
        headers = {}
        url = "https://example.com/article"
        content_type = "text/html"
        charset = "utf-8"
        content = FakeContent()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        def get(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(
        "orinoco.research.webpage.aiohttp.ClientSession",
        lambda **kwargs: FakeSession(),
    )

    async def run() -> None:
        with pytest.raises(SafeFetchError, match="2 MiB limit"):
            await research_routes.fetch_public_page("https://example.com/article")

    asyncio.run(run())
