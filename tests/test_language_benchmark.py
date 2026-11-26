"""Tests for the local-only Welsh/English Ollama benchmark runner."""
from __future__ import annotations

import json
import threading
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from scripts.benchmark_languages import CASES, ask_ollama, local_endpoint


def test_endpoint_accepts_loopback_only() -> None:
    assert local_endpoint("http://127.0.0.1:11434/") == "http://127.0.0.1:11434"
    assert local_endpoint("http://localhost:11434") == "http://localhost:11434"
    assert local_endpoint("http://[::1]:11434") == "http://[::1]:11434"


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:11434",
        "http://ollama.example:11434",
        "http://192.168.1.20:11434",
        "http://127.0.0.1:11434/api",
        "http://127.0.0.1:11434/?token=secret",
    ],
)
def test_endpoint_rejects_non_loopback_or_extra_url_parts(url: str) -> None:
    with pytest.raises(ValueError):
        local_endpoint(url)


def test_prompt_pairs_cover_both_languages() -> None:
    pairs: dict[str, set[str]] = {}
    for case in CASES:
        pairs.setdefault(case["id"], set()).add(case["language"])
    assert len(CASES) >= 12
    assert all({"en", "cy"} <= languages for case_id, languages in pairs.items() if case_id != "code_switch")
    assert {"cy-en", "en-cy"} <= pairs["code_switch"]


def make_server(status: int = 200, location: str | None = None):
    received: dict[str, object] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            received["path"] = self.path
            received["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            self.send_response(status)
            if location:
                self.send_header("Location", location)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            if status == 200:
                self.wfile.write(json.dumps({"message": {"content": "Helo!"}}).encode())

        def log_message(self, format: str, *args: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, received


def stop_server(server: HTTPServer, thread: threading.Thread) -> None:
    server.shutdown()
    thread.join(timeout=2)
    server.server_close()


def test_ask_ollama_posts_expected_payload_to_local_api() -> None:
    server, thread, received = make_server()
    try:
        endpoint = f"http://127.0.0.1:{server.server_port}"
        answer = ask_ollama(endpoint, "qwen2.5:1.5b", "Helo", 2048, 5)
        assert answer == "Helo!"
        assert received["path"] == "/api/chat"
        body = received["body"]
        assert body["model"] == "qwen2.5:1.5b"
        assert body["stream"] is False
        assert body["options"]["num_ctx"] == 2048
    finally:
        stop_server(server, thread)


def test_ask_ollama_refuses_redirects() -> None:
    server, thread, _ = make_server(status=302, location="http://example.com/")
    try:
        endpoint = f"http://127.0.0.1:{server.server_port}"
        with pytest.raises(urllib.error.HTTPError):
            ask_ollama(endpoint, "test-model", "test", 1024, 5)
    finally:
        stop_server(server, thread)
