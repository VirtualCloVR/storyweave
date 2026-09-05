from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app import api
from app.db import get_db
from app.main import app
from app.models import Message, Source
from app.tools import FetchResult


def _session(client: TestClient) -> str:
    project = client.post("/api/projects", json={"title": "Web project"}).json()
    thread = client.post(f"/api/projects/{project['id']}/threads", json={"title": "Web thread"}).json()
    session = client.post(f"/api/threads/{thread['id']}/sessions", json={"title": "Research"}).json()
    return session["id"]


def test_web_search_persists_source_metadata(db, monkeypatch):
    app.dependency_overrides[get_db] = lambda: db
    result = FetchResult(
        url="https://example.com/article", title="Example article", text="A fetched excerpt",
        query="事故の現実性", source_type="search", fetched_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(api, "search_and_fetch", lambda query: _async_result([result]))
    try:
        client = TestClient(app)
        session_id = _session(client)
        response = client.post(f"/api/sessions/{session_id}/web-search", json={"query": "事故の現実性"})
        assert response.status_code == 200
        source = response.json()[0]
        assert source["url"] == result.url
        assert source["title"] == result.title
        assert source["fetchedAt"].startswith("2025-01-01")
        assert source["sourceType"] == "search"
        assert source["query"] == "事故の現実性"
        assert db.query(Source).count() == 1
    finally:
        app.dependency_overrides.clear()


def test_chat_sse_returns_and_links_sources_to_assistant(db, monkeypatch):
    app.dependency_overrides[get_db] = lambda: db
    result = FetchResult(url="https://example.com/a", title="A", text="grounded text", query="query", source_type="search")

    async def fake_search(query):
        return [result]

    async def fake_stream(messages):
        assert "grounded text" in messages[0]["content"]
        yield "answer"

    monkeypatch.setattr(api, "search_and_fetch", fake_search)
    monkeypatch.setattr(api.llm, "stream_completion", fake_stream)
    try:
        client = TestClient(app)
        session_id = _session(client)
        response = client.post(
            f"/api/sessions/{session_id}/chat",
            json={"content": "queryについてwebから検索して"},
        )
        assert response.status_code == 200
        assert "event: done" in response.text
        assert "https://example.com/a" in response.text
        assistant = db.query(Message).filter(Message.role == "assistant").one()
        source = db.query(Source).one()
        assert source.message_id == assistant.id
        saved_messages = client.get(f"/api/sessions/{session_id}/messages").json()
        assert saved_messages[-1]["sources"][0]["url"] == "https://example.com/a"
    finally:
        app.dependency_overrides.clear()


def _async_result(value):
    async def result():
        return value
    return result()
