"""Small asynchronous client for Orinoco's private local Ollama service."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import httpx


class OllamaError(RuntimeError):
    """Raised when the local Ollama service cannot complete a chat request."""


class OllamaClient:
    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "qwen2.5:1.5b",
        context_length: int = 2048,
        timeout: float = 600.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not 1024 <= context_length <= 8192:
            raise ValueError("context_length must be between 1024 and 8192")
        if not model:
            raise ValueError("model must not be empty")

        self.model = model
        self.context_length = context_length
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            transport=transport,
        )

    async def chat(self, messages: Sequence[dict[str, str]]) -> str:
        if not messages:
            raise ValueError("at least one message is required")

        safe_messages: list[dict[str, str]] = []
        for message in messages:
            role = message.get("role")
            content = message.get("content")
            if role not in {"system", "user", "assistant"}:
                raise ValueError("message role must be system, user or assistant")
            if not isinstance(content, str) or not content.strip():
                raise ValueError("message content must be a non-empty string")
            if len(content) > 16000:
                raise ValueError("message content exceeds the 16000-character limit")
            safe_messages.append({"role": role, "content": content})

        try:
            response = await self._client.post(
                "/api/chat",
                json={
                    "model": self.model,
                    "messages": safe_messages,
                    "stream": False,
                    "options": {"num_ctx": self.context_length},
                },
            )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise OllamaError("The local Ollama service did not return a valid response.") from exc

        message = payload.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            raise OllamaError("The local Ollama service returned an unexpected response.")

        return content

    async def aclose(self) -> None:
        await self._client.aclose()
