"""Tests for the local Ollama client."""

import asyncio
import json

import httpx
import pytest

from orinoco.llm.ollama import OllamaClient, OllamaError


def test_chat_sends_non_streaming_request_and_returns_content(monkeypatch) -> None:
    from orinoco.llm import ollama as ollama_module

    monkeypatch.setattr(ollama_module, "resolve_ai_threads", lambda: 2)
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
    assert payload["options"] == {"num_ctx": 2048, "num_predict": 512, "num_thread": 2}


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


def test_environment_cannot_redirect_inference_to_remote_provider(monkeypatch) -> None:
    """The default inference endpoint remains loopback even if an env override is present."""
    monkeypatch.setenv("ORINOCO_OLLAMA_API", "https://remote-inference.example/api")
    client = OllamaClient()
    try:
        assert str(client._client.base_url) == "http://127.0.0.1:11434"
        assert client._client._trust_env is False
    finally:
        asyncio.run(client.aclose())


def test_production_client_rejects_explicit_remote_inference_url() -> None:
    with pytest.raises(ValueError, match="must be loopback"):
        OllamaClient(base_url="https://remote-inference.example/api")


def test_context_budget_keeps_latest_prompt_and_trims_old_history_and_references() -> None:
    """Older history and reference snippets are trimmed before the current request."""
    from orinoco.llm.ollama import _fit_messages_to_context

    messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "O" * 1000},
        {"role": "assistant", "content": "R" * 600},
        {
            "role": "user",
            "content": "[ORINOCO REFERENCE CONTEXT]\n" + "D" * 1000,
        },
        {"role": "user", "content": "latest"},
    ]

    fitted = _fit_messages_to_context(messages, 1024)
    total_bytes = sum(len(item["content"].encode("utf-8")) for item in fitted)

    assert fitted[0] == messages[0]
    assert fitted[-1] == messages[-1]
    assert fitted[1]["content"].startswith("[Earlier conversation context shortened]")
    assert fitted[2]["content"] == "R" * 600
    assert fitted[3]["content"].endswith("[Reference context shortened to fit the model context.]")
    assert total_bytes <= int((1024 - 512 - 64) * 3.5)


def test_context_budget_rejects_system_and_latest_prompt_that_cannot_fit() -> None:
    """Never silently truncate the current user request or system instructions."""
    from orinoco.llm.ollama import OllamaContextError, _fit_messages_to_context

    messages = [
        {"role": "system", "content": "S" * 1000},
        {"role": "user", "content": "U" * 1000},
    ]

    with pytest.raises(OllamaContextError, match="Shorten it or increase MODEL_CONTEXT"):
        _fit_messages_to_context(messages, 1024)


def test_client_rejects_oversized_context_before_network_call() -> None:
    """A context overflow is a local validation error, not a model connectivity error."""
    async def run() -> None:
        client = OllamaClient(
            context_length=1024,
            transport=httpx.MockTransport(lambda _: pytest.fail("unexpected request")),
        )
        try:
            with pytest.raises(OllamaContextError):
                await client.chat([
                    {"role": "system", "content": "S" * 1000},
                    {"role": "user", "content": "U" * 1000},
                ])
        finally:
            await client.aclose()

    from orinoco.llm.ollama import OllamaContextError

    asyncio.run(run())
