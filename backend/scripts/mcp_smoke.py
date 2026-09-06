import asyncio
import os

from app.tools.mcp_client import McpWebClient


async def main() -> None:
    command = os.environ.get("MCP_SEARCH_COMMAND", "/usr/local/bin/python")
    server_path = os.environ.get("MCP_SEARCH_SERVER_PATH", "/opt/mcp-searxng/server.py")
    client = McpWebClient(command, server_path, timeout=35, max_chars=3000)
    stack, session = await client._open()
    try:
        tools = sorted(tool.name for tool in (await session.list_tools()).tools)
        search = client._tool_value(await session.call_tool(
            "web_search", arguments={"query": "Ollama official website", "max_results": 5},
        ))
        fetched = client._tool_value(await session.call_tool(
            "fetch_page", arguments={"url": "https://ollama.com/", "max_chars": 3000},
        ))
    finally:
        await stack.aclose()
    if isinstance(search, dict):
        search = search.get("results", search.get("items", []))
    search_count = len(search) if isinstance(search, list) else -1
    fetch_chars = len(fetched.get("content", "")) if isinstance(fetched, dict) else -1
    print(f"tools={','.join(tools)}")
    print(f"web_search_results={search_count}")
    print(f"fetch_page_chars={fetch_chars}")
    if tools != ["fetch_page", "web_search"] or search_count < 1 or fetch_chars <= 0:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
