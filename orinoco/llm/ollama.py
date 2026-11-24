"""Small asynchronous client for Orinoco's private local Ollama service."""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any

import httpx


class OllamaError(RuntimeError):
    """Raised when the local Ollama service cannot complete a chat request."""


class OllamaClient:
    """Send validated chat messages to the local Ollama service; no external inference provider is used."""
    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        context_length: int | None = None,
        timeout: float = 600.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        resolved_model = model or os.environ.get("AI_MODEL", "qwen2.5:1.5b")
        resolved_context = (
            context_length
            if context_length is not None
            else int(os.environ.get("MODEL_CONTEXT", "2048"))
        )
        # Production inference is intentionally local-only. Tests may inject an
        # explicit mock base_url, but environment variables cannot redirect user
        # prompts to an external inference provider.
        resolved_url = base_url or "http://127.0.0.1:11434"

        if not 1024 <= resolved_context <= 8192:
            raise ValueError("context_length must be between 1024 and 8192")
        if not resolved_model:
            raise ValueError("model must not be empty")

        self.model = resolved_model
        self.context_length = resolved_context
        self._client = httpx.AsyncClient(
            base_url=resolved_url.rstrip("/"),
            timeout=timeout,
            transport=transport,
        )

    async def chat(self, messages: Sequence[dict[str, str]]) -> str:
        """Validate and send chat messages to the local Ollama API."""
        if not messages:
            raise ValueError("at least one message is required")

        safe_messages: list[dict[str, str]] = []
        for message in messages:
            if not isinstance(message, dict):
                raise ValueError("each message must be an object")
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
                    "options": {"num_ctx": self.context_length, "num_predict": 512},
                },
            )
            response.raise_for_status()
            payload: Any = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise OllamaError("The local Ollama service did not return a valid response.") from exc

        if not isinstance(payload, dict):
            raise OllamaError("The local Ollama service returned an unexpected response.")

        message = payload.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            raise OllamaError("The local Ollama service returned an unexpected response.")

        return content

    async def aclose(self) -> None:
        """Release the HTTP client and its pooled connections."""
        await self._client.aclose()
