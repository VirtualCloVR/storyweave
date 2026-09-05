import ipaddress
import socket
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP


mcp = FastMCP("searxng-search")

SEARXNG_URL = "http://192.168.11.7:8080/search"
MAX_RESPONSE_BYTES = 2_000_000


def validate_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Only credential-free HTTP(S) URLs are allowed")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    for info in socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM):
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise ValueError("Private, loopback, link-local, and reserved addresses are blocked")


@mcp.tool()
def web_search(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Search the web using local SearXNG and return title, url, and snippet."""
    max_results = max(1, min(max_results, 10))
    response = requests.get(
        SEARXNG_URL,
        params={"q": query, "format": "json"},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    return [
        {
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "content": item.get("content", ""),
            "engine": item.get("engine", ""),
        }
        for item in data.get("results", [])[:max_results]
    ]


@mcp.tool()
def fetch_page(url: str, max_chars: int = 8000) -> dict[str, Any]:
    """Fetch a web page and return readable text."""
    max_chars = max(1000, min(max_chars, 20_000))
    validate_public_url(url)
    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; local-mcp-fetch/1.0)"},
        timeout=30,
        allow_redirects=False,
        stream=True,
    )
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").lower()
    if "text/html" not in content_type and "text/plain" not in content_type:
        raise ValueError("Unsupported content type")
    content = bytearray()
    for chunk in response.iter_content(chunk_size=65_536):
        content.extend(chunk)
        if len(content) > MAX_RESPONSE_BYTES:
            raise ValueError("Response exceeds configured size limit")
    encoding = response.encoding or "utf-8"
    soup = BeautifulSoup(bytes(content).decode(encoding, errors="replace"), "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "header", "footer", "nav"]):
        tag.decompose()
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    lines = [line.strip() for line in soup.get_text("\n").splitlines() if line.strip()]
    text = "\n".join(lines)
    return {
        "url": url,
        "title": title,
        "content": text[:max_chars],
        "truncated": len(text) > max_chars,
    }


if __name__ == "__main__":
    mcp.run()
