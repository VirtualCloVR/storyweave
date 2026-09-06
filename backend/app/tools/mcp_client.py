"""stdio MCP client for the existing SearXNG search server."""

import asyncio
import json
import os
from contextlib import AsyncExitStack
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .base import FetchResult
from .fetch import SafeWebFetcher


class McpWebClient:
    def __init__(
        self,
        command: str,
        server_path: str,
        *,
        timeout: float = 20,
        max_chars: int = 8000,
        allowed_hosts: set[str] | None = None,
    ):
        self.command = command
        self.server_path = server_path
        self.timeout = timeout
        self.max_chars = min(max(max_chars, 1), 20_000)
        self.validator = SafeWebFetcher(allowed_hosts or set(), timeout=timeout)

    @property
    def available(self) -> bool:
        return Path(self.command).is_file() and Path(self.server_path).is_file()

    @staticmethod
    def _server_environment() -> dict[str, str]:
        # The MCP SDK intentionally inherits only a small safe allowlist.
        # Pass the one setting required by the SearXNG child explicitly.
        searxng_url = os.environ.get("SEARXNG_URL", "").strip()
        return {"SEARXNG_URL": searxng_url} if searxng_url else {}

    async def _open(self) -> tuple[AsyncExitStack, ClientSession]:
        stack = AsyncExitStack()
        try:
            read, write = await stack.enter_async_context(stdio_client(
                StdioServerParameters(
                    command=self.command,
                    args=[self.server_path],
                    env=self._server_environment(),
                ),
            ))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            listed = await session.list_tools()
            names = {tool.name for tool in listed.tools}
            missing = {"web_search", "fetch_page"} - names
            if missing:
                raise RuntimeError(f"MCP server is missing required tools: {', '.join(sorted(missing))}")
        except Exception:
            await stack.aclose()
            raise
        return stack, session

    @staticmethod
    def _tool_value(result: Any) -> Any:
        def normalize(value: Any) -> Any:
            if hasattr(value, "model_dump"):
                value = value.model_dump(by_alias=True)
            if isinstance(value, dict) and "result" in value:
                return normalize(value["result"])
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            return value

        # The Python SDK has used both camelCase and snake_case fields, and
        # some versions expose only a model-dump mapping.
        result_map = result.model_dump(by_alias=True) if hasattr(result, "model_dump") else result if isinstance(result, dict) else None
        structured = (
            getattr(result, "structuredContent", None)
            or getattr(result, "structured_content", None)
            or (result_map or {}).get("structuredContent")
            or (result_map or {}).get("structured_content")
        )
        if structured:
            # FastMCP/mcp versions may add metadata alongside the result
            # envelope or serialize the wrapped value as JSON text.
            return normalize(structured)
        content = getattr(result, "content", None) or (result_map or {}).get("content", [])
        for item in content:
            text = getattr(item, "text", None)
            if text is None and isinstance(item, dict):
                text = item.get("text")
            if not text:
                continue
            return normalize(text)
        return None

    async def search_and_fetch(self, query: str, max_results: int = 3) -> list[FetchResult]:
        if not self.available:
            raise RuntimeError(f"MCP command or server was not found: {self.command} {self.server_path}")
        async with asyncio.timeout(self.timeout * (max_results + 2)):
            stack, session = await self._open()
            try:
                search_result = await session.call_tool("web_search", arguments={"query": query, "max_results": min(max_results * 2, 10)})
                raw_results = self._tool_value(search_result)
                if isinstance(raw_results, dict):
                    raw_results = raw_results.get("results", raw_results.get("items", []))
                if not isinstance(raw_results, list):
                    return []
                fetched: list[FetchResult] = []
                for item in raw_results:
                    if not isinstance(item, dict) or not isinstance(item.get("url"), str):
                        continue
                    url = item["url"]
                    try:
                        self.validator.validate_url(url)
                        page_result = await session.call_tool("fetch_page", arguments={"url": url, "max_chars": self.max_chars})
                        page = self._tool_value(page_result)
                    except Exception:
                        continue
                    if not isinstance(page, dict) or not isinstance(page.get("content"), str) or not page["content"].strip():
                        continue
                    fetched.append(FetchResult(
                        url=str(page.get("url") or url),
                        title=str(page.get("title") or item.get("title") or url),
                        text=page["content"],
                        fetched_at=datetime.now(timezone.utc),
                        query=query,
                        source_type="search",
                        provider="mcp-searxng",
                    ))
                    if len(fetched) >= max_results:
                        break
                return fetched
            finally:
                await stack.aclose()

    async def fetch_url(self, url: str) -> FetchResult:
        if not self.available:
            raise RuntimeError(f"MCP command or server was not found: {self.command} {self.server_path}")
        self.validator.validate_url(url)
        async with asyncio.timeout(self.timeout * 2):
            stack, session = await self._open()
            try:
                result = self._tool_value(await session.call_tool("fetch_page", arguments={"url": url, "max_chars": self.max_chars}))
            finally:
                await stack.aclose()
        if not isinstance(result, dict) or not isinstance(result.get("content"), str) or not result["content"].strip():
            raise RuntimeError("MCP fetch_page returned no readable content")
        return FetchResult(
            url=str(result.get("url") or url),
            title=str(result.get("title") or url),
            text=result["content"],
            fetched_at=datetime.now(timezone.utc),
            source_type="fetch",
            provider="mcp-searxng",
        )
