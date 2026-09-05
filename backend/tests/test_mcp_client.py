import json

from app.tools.mcp_client import McpWebClient


def test_tool_value_accepts_fastmcp_text_payload():
    class Text:
        text = json.dumps([{"title": "Example", "url": "https://example.com"}])

    class Result:
        structuredContent = None
        content = [Text()]

    assert McpWebClient._tool_value(Result())[0]["url"] == "https://example.com"


def test_tool_value_unwraps_fastmcp_structured_result():
    class Result:
        structuredContent = {"result": {"url": "https://example.com", "content": "body"}}
        content = []

    assert McpWebClient._tool_value(Result())["content"] == "body"
