"""Swappable web search implementation.

The provider deliberately returns the same FetchResult shape as URL fetching so
every result can be persisted as a Source with its URL, title and timestamp.
"""
from urllib.parse import parse_qs, quote_plus, urlparse

import httpx
from bs4 import BeautifulSoup

from .base import FetchResult


class DuckDuckGoSearchProvider:
    """Small HTML adapter with no API key requirement.

    Deployments can replace this class through ``SearchProvider`` injection;
    this adapter is only a useful safe default for a LAN-only MVP.
    """

    def __init__(self, endpoint: str = "https://html.duckduckgo.com/html/", timeout: float = 10, max_bytes: int = 2_000_000):
        self.endpoint = endpoint
        self.timeout = timeout
        self.max_bytes = max_bytes

    async def search_web(self, query: str) -> list[FetchResult]:
        if not query.strip():
            return []
        url = f"{self.endpoint}?q={quote_plus(query.strip())}"
        content = bytearray()
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
            async with client.stream("GET", url, headers={"User-Agent": "Storyweave/0.1"}) as response:
                response.raise_for_status()
                if "text/html" not in response.headers.get("content-type", "").lower():
                    raise ValueError("Search provider returned an unsupported content type")
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > self.max_bytes:
                        raise ValueError("Search response exceeds configured size limit")
        soup = BeautifulSoup(bytes(content), "html.parser")
        results: list[FetchResult] = []
        for node in soup.select(".result"):
            link = node.select_one(".result__a[href]")
            if link is None:
                continue
            href = str(link.get("href", "")).strip()
            parsed = urlparse("https:" + href if href.startswith("//") else href)
            if parsed.hostname and parsed.hostname.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
                href = parse_qs(parsed.query).get("uddg", [""])[0]
            title = link.get_text(" ", strip=True) or None
            snippet_node = node.select_one(".result__snippet")
            excerpt = snippet_node.get_text(" ", strip=True) if snippet_node else ""
            if href.startswith(("http://", "https://")):
                results.append(FetchResult(url=href, title=title, text=excerpt, query=query, source_type="search"))
        return results
