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


def test_tool_value_unwraps_structured_result_with_metadata():
    class Result:
        structured_content = {"result": [{"url": "https://example.com"}], "_meta": {}}
        content = []

    assert McpWebClient._tool_value(Result())[0]["url"] == "https://example.com"


def test_tool_value_accepts_mapping_result_payload():
    payload = {"content": [{"type": "text", "text": json.dumps([{"url": "https://example.com"}])}]}
    assert McpWebClient._tool_value(payload)[0]["url"] == "https://example.com"


def test_tool_value_decodes_json_text_in_structured_result():
    class Result:
        structured_content = {"result": json.dumps([{"url": "https://example.com"}]), "_meta": {}}
        content = []

    assert McpWebClient._tool_value(Result())[0]["url"] == "https://example.com"


def test_server_environment_passes_only_searxng_url(monkeypatch):
    monkeypatch.setenv("SEARXNG_URL", "http://host.docker.internal:8080")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-inherited")

    assert McpWebClient._server_environment() == {
        "SEARXNG_URL": "http://host.docker.internal:8080",
    }
