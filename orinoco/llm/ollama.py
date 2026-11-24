"""Small asynchronous client for Orinoco's private local Ollama service."""

from __future__ import annotations

import os
from urllib.parse import urlsplit
from collections.abc import Sequence
from typing import Any

import httpx


class OllamaError(RuntimeError):
    """Raised when the local Ollama service cannot complete a chat request."""


class OllamaContextError(OllamaError):
    """Raised when the current request cannot fit inside the configured model context."""


_OUTPUT_TOKEN_RESERVE = 512
_CONTEXT_OVERHEAD_TOKENS = 64
_ESTIMATED_BYTES_PER_TOKEN = 3.5
_REFERENCE_CONTEXT_SHARE = 0.35
_MIN_PARTIAL_HISTORY_BYTES = 256


def _truncate_utf8(value: str, maximum_bytes: int, *, keep_end: bool = False) -> str:
    """Trim UTF-8 text without returning a broken multi-byte character."""
    if maximum_bytes <= 0:
        return ""
    encoded = value.encode("utf-8")
    if len(encoded) <= maximum_bytes:
        return value
    selected = encoded[-maximum_bytes:] if keep_end else encoded[:maximum_bytes]
    return selected.decode("utf-8", errors="ignore")


def _fit_messages_to_context(
    messages: list[dict[str, str]],
    context_length: int,
) -> list[dict[str, str]]:
    """Keep system/latest messages and trim older history/reference data to a safe budget."""
    prompt_budget = int(
        (context_length - _OUTPUT_TOKEN_RESERVE - _CONTEXT_OVERHEAD_TOKENS)
        * _ESTIMATED_BYTES_PER_TOKEN
    )
    if len(messages) == 1 and messages[0]["role"] == "system":
        if len(messages[0]["content"].encode("utf-8")) > prompt_budget:
            raise OllamaContextError(
                "Orinoco's system instructions exceed the configured model context. "
                "Increase MODEL_CONTEXT."
            )
        return messages

    system_messages = messages[:1] if messages and messages[0]["role"] == "system" else []
    latest_message = messages[-1:]
    middle_messages = messages[len(system_messages):-1]
    base_bytes = sum(len(item["content"].encode("utf-8")) for item in system_messages + latest_message)
    if base_bytes > prompt_budget:
        raise OllamaContextError(
            "Your current message is too long for the configured model context. "
            "Shorten it or increase MODEL_CONTEXT."
        )

    remaining = prompt_budget - base_bytes
    reference_messages = [
        item for item in middle_messages
        if item["role"] == "user" and item["content"].startswith("[ORINOCO REFERENCE CONTEXT")
    ]
    history_messages = [item for item in middle_messages if item not in reference_messages]

    # References are useful, but reserve at least half of the remaining budget
    # for recent conversation history.
    reference_budget = min(remaining // 2, int(prompt_budget * _REFERENCE_CONTEXT_SHARE))
    selected_references: list[dict[str, str]] = []
    truncation_marker = "\n[Reference context shortened to fit the model context.]"
    for item in reference_messages:
        if reference_budget < 128:
            break
        content_bytes = len(item["content"].encode("utf-8"))
        if content_bytes <= reference_budget:
            selected_references.append(item)
            reference_budget -= content_bytes
            remaining -= content_bytes
            continue
        content_budget = reference_budget - len(truncation_marker.encode("utf-8"))
        shortened = _truncate_utf8(item["content"], content_budget)
        if shortened:
            selected_references.append(
                {"role": item["role"], "content": shortened + truncation_marker}
            )
            used = len(selected_references[-1]["content"].encode("utf-8"))
            remaining -= used
        break

    selected_history: list[dict[str, str]] = []
    history_marker = "[Earlier conversation context shortened]\n"
    for item in reversed(history_messages):
        content_bytes = len(item["content"].encode("utf-8"))
        if content_bytes <= remaining:
            selected_history.append(item)
            remaining -= content_bytes
            continue
        if remaining >= _MIN_PARTIAL_HISTORY_BYTES:
            content_budget = remaining - len(history_marker.encode("utf-8"))
            shortened = _truncate_utf8(item["content"], content_budget, keep_end=True)
            if shortened:
                selected_history.append(
                    {"role": item["role"], "content": history_marker + shortened}
                )
        break

    selected_history.reverse()
    return system_messages + selected_history + selected_references + latest_message


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
        if transport is None:
            parsed_url = urlsplit(resolved_url)
            if (
                parsed_url.scheme != "http"
                or parsed_url.hostname not in {"127.0.0.1", "::1", "localhost"}
                or parsed_url.port != 11434
                or parsed_url.username
                or parsed_url.password
                or parsed_url.query
                or parsed_url.fragment
            ):
                raise ValueError("the production Ollama endpoint must be loopback on port 11434")

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
            trust_env=False,
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

        fitted_messages = _fit_messages_to_context(safe_messages, self.context_length)
        try:
            response = await self._client.post(
                "/api/chat",
                json={
                    "model": self.model,
                    "messages": fitted_messages,
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
