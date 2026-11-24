"""Bounded public-web fetching with DNS-pinned public-address resolution."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import aiohttp
from aiohttp.abc import AbstractResolver
from bs4 import BeautifulSoup

MAX_PAGE_BYTES = 2 * 1024 * 1024
MAX_PAGE_TEXT = 16_000
MAX_REDIRECTS = 3
_ALLOWED_PORTS = {80, 443}
_BLOCKED_SUFFIXES = (".localhost", ".local", ".internal", ".test", ".invalid")


class SafeFetchError(RuntimeError):
    """Raised when a URL is invalid, unsafe or cannot be read."""


@dataclass(frozen=True)
class FetchedPage:
    url: str
    title: str
    text: str


def validate_url_syntax(url: str) -> tuple[str, str, int]:
    parsed = urlsplit(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SafeFetchError("Only public HTTP and HTTPS website URLs are supported.")
    if parsed.username or parsed.password:
        raise SafeFetchError("Website URLs must not contain embedded credentials.")
    host = parsed.hostname.rstrip(".").lower()
    if host == "localhost" or host.endswith(_BLOCKED_SUFFIXES):
        raise SafeFetchError("Private and local network addresses cannot be opened.")
    try:
        literal_ip = ipaddress.ip_address(host)
    except ValueError:
        literal_ip = None
    if literal_ip is not None and not literal_ip.is_global:
        raise SafeFetchError("Private and local network addresses cannot be opened.")
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise SafeFetchError("The website URL contains an invalid port.") from exc
    if port not in _ALLOWED_PORTS:
        raise SafeFetchError("Only standard HTTP and HTTPS ports are supported.")
    return parsed.scheme, host, port


class PublicResolver(AbstractResolver):
    """Resolve a hostname once per connection and reject non-public IP addresses."""

    async def resolve(
        self,
        host: str,
        port: int = 0,
        family: int = socket.AF_INET,
    ) -> list[dict[str, object]]:
        host_for_url = f"[{host}]" if ":" in host and not host.startswith("[") else host
        _, hostname, checked_port = validate_url_syntax(
            f"https://{host_for_url}:{port or 443}/"
        )
        loop = asyncio.get_running_loop()
        try:
            literal = ipaddress.ip_address(hostname)
            addresses = [(socket.AF_INET6 if literal.version == 6 else socket.AF_INET, str(literal))]
        except ValueError:
            infos = await loop.getaddrinfo(
                hostname,
                checked_port,
                family=family if family in {socket.AF_INET, socket.AF_INET6} else socket.AF_UNSPEC,
                type=socket.SOCK_STREAM,
            )
            addresses = []
            for address_family, _, _, _, sockaddr in infos:
                addresses.append((address_family, sockaddr[0]))

        unique: dict[tuple[int, str], None] = {}
        for address_family, address in addresses:
            ip = ipaddress.ip_address(address)
            if not ip.is_global:
                raise OSError("The website hostname resolved to a non-public IP address.")
            unique[(address_family, address)] = None

        if not unique:
            raise OSError("The website hostname did not resolve to a public IP address.")

        return [
            {
                "hostname": hostname,
                "host": address,
                "port": checked_port,
                "family": address_family,
                "proto": socket.IPPROTO_TCP,
                "flags": 0,
            }
            for address_family, address in unique
        ]

    async def close(self) -> None:
        return None


def _extract_readable_text(content: bytes, content_type: str, charset: str | None) -> tuple[str, str]:
    encoding = charset or "utf-8"
    try:
        raw = content.decode(encoding, errors="replace")
    except LookupError:
        raw = content.decode("utf-8", errors="replace")
    if content_type in {"text/plain"}:
        return "", raw[:MAX_PAGE_TEXT]

    soup = BeautifulSoup(raw, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    for element in soup(["script", "style", "nav", "footer", "header", "aside", "form", "noscript", "svg", "iframe"]):
        element.decompose()
    text = "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())
    return title[:240], text[:MAX_PAGE_TEXT]


async def fetch_public_page(url: str) -> FetchedPage:
    current = url.strip()
    connector = aiohttp.TCPConnector(
        resolver=PublicResolver(),
        use_dns_cache=False,
        limit=1,
        ssl=True,
    )
    timeout = aiohttp.ClientTimeout(total=15, connect=5, sock_read=8)
    headers = {
        "User-Agent": "Orinoco/0.1 (+self-hosted assistant; webpage summary request)",
        "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9",
    }

    try:
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=headers,
            trust_env=False,
            auto_decompress=True,
        ) as session:
            for redirect_count in range(MAX_REDIRECTS + 1):
                validate_url_syntax(current)
                async with session.get(current, allow_redirects=False) as response:
                    if response.status in {301, 302, 303, 307, 308}:
                        location = response.headers.get("Location")
                        if not location or redirect_count >= MAX_REDIRECTS:
                            raise SafeFetchError("The website redirected too many times.")
                        current = urljoin(current, location)
                        continue
                    if response.status < 200 or response.status >= 300:
                        raise SafeFetchError(f"The website returned HTTP {response.status}.")
                    content_type = response.content_type.lower()
                    if content_type not in {"text/html", "application/xhtml+xml", "text/plain"}:
                        raise SafeFetchError("This link does not point to a readable webpage or text file.")

                    chunks: list[bytes] = []
                    total = 0
                    async for chunk in response.content.iter_chunked(64 * 1024):
                        total += len(chunk)
                        if total > MAX_PAGE_BYTES:
                            raise SafeFetchError("The webpage is larger than the 2 MiB limit.")
                        chunks.append(chunk)
                    body = b"".join(chunks)
                    title, text = _extract_readable_text(body, content_type, response.charset)
                    if len(text.strip()) < 40:
                        raise SafeFetchError("The webpage did not contain enough readable text to summarise.")
                    return FetchedPage(url=str(response.url), title=title, text=text)
    except SafeFetchError:
        raise
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError, UnicodeError, LookupError) as exc:
        raise SafeFetchError("The webpage could not be fetched safely.") from exc

    raise SafeFetchError("The webpage could not be fetched safely.")
