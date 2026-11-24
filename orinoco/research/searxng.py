"""Minimal client for a configured self-hosted SearXNG instance."""

from __future__ import annotations

import ipaddress
import os
from urllib.parse import urlparse

import httpx


class SearchUnavailable(RuntimeError):
    """Raised when web search is disabled or its configured service fails."""


class SearXNGClient:
    """Query an administrator-configured SearXNG instance without external inference."""
    def __init__(
        self,
        *,
        base_url: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """Validate the configured endpoint and create a bounded async HTTP client."""
        self.base_url = (base_url or os.environ.get("SEARXNG_URL", "")).strip().rstrip("/")
        if os.environ.get("ENABLE_WEB_SEARCH", "false").lower() in {"0", "false", "no", "off"}:
            raise SearchUnavailable("Web search is disabled by the administrator.")
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise SearchUnavailable("Web search has not been configured by the administrator.")
        if parsed.username or parsed.password:
            raise SearchUnavailable("The configured search URL is invalid.")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=20.0,
            follow_redirects=False,
            trust_env=False,
            transport=transport,
            headers={"Accept": "application/json", "User-Agent": "Orinoco/0.1"},
        )

    async def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        """Return a small, validated set of public HTTP(S) search results."""
        clean_query = " ".join(query.split())
        if len(clean_query) < 3 or len(clean_query) > 300:
            raise ValueError("Search queries must be between 3 and 300 characters.")
        try:
            response = await self._client.get(
                "/search",
                params={"q": clean_query, "format": "json", "categories": "general"},
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise SearchUnavailable("The configured search service did not return valid results.") from exc

        raw_results = payload.get("results", []) if isinstance(payload, dict) else []
        results: list[dict[str, str]] = []
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            if not isinstance(url, str):
                continue
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                continue
            if parsed.username or parsed.password:
                continue
            hostname = parsed.hostname.rstrip(".").lower()
            if hostname == "localhost" or hostname.endswith((
                ".localhost", ".local", ".internal", ".lan", ".home.arpa",
                ".test", ".example", ".invalid",
            )):
                continue
            try:
                port = parsed.port
            except ValueError:
                continue
            try:
                address = ipaddress.ip_address(hostname)
            except ValueError:
                address = None
            if address is not None and not address.is_global:
                continue
            title = " ".join(str(item.get("title") or "Untitled result").split())[:240]
            content = " ".join(str(item.get("content") or "").split())[:700]
            results.append({
                "title": title,
                "url": url,
                "content": content,
                "engine": "SearXNG",
            })
            if len(results) >= max(1, min(limit, 8)):
                break
        return results

    async def aclose(self) -> None:
        """Release the underlying HTTP connection pool."""
        await self._client.aclose()
