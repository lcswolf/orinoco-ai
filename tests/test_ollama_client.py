"""Tests for the local Ollama client."""

import asyncio
import json

import httpx
import pytest

from orinoco.llm.ollama import OllamaClient, OllamaError


def test_chat_sends_non_streaming_request_and_returns_content() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"message": {"role": "assistant", "content": "Hello from Orinoco."}},
        )

    async def run() -> str:
        client = OllamaClient(transport=httpx.MockTransport(handler))
        try:
            return await client.chat([{"role": "user", "content": "Hello"}])
        finally:
            await client.aclose()

    result = asyncio.run(run())

    assert result == "Hello from Orinoco."
    assert seen["path"] == "/api/chat"
    payload = seen["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == "qwen2.5:1.5b"
    assert payload["stream"] is False
    assert payload["options"] == {"num_ctx": 2048, "num_predict": 512}


def test_chat_rejects_unsupported_roles_before_network_call() -> None:
    async def run() -> None:
        client = OllamaClient(transport=httpx.MockTransport(lambda _: pytest.fail("unexpected request")))
        try:
            with pytest.raises(ValueError):
                await client.chat([{"role": "tool", "content": "not allowed"}])
        finally:
            await client.aclose()

    asyncio.run(run())


def test_chat_converts_http_errors_to_ollama_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "busy"})

    async def run() -> None:
        client = OllamaClient(transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(OllamaError):
                await client.chat([{"role": "user", "content": "Hello"}])
        finally:
            await client.aclose()

    asyncio.run(run())


def test_context_length_is_bounded() -> None:
    with pytest.raises(ValueError):
        OllamaClient(context_length=16384)
