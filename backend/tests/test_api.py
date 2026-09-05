from fastapi.testclient import TestClient
from app.db import get_db
from app.main import app

def test_crud_and_search(db):
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        project = client.post("/api/projects", json={"title": "星の物語"}).json()
        assert project["title"] == "星の物語"
        thread = client.post(f"/api/projects/{project['id']}/threads", json={"title": "第一話"}).json()
        session = client.post(f"/api/threads/{thread['id']}/sessions", json={"title": "主人公の動機"}).json()
        rejected = client.patch(f"/api/sessions/{session['id']}", json={"status": "adopted", "pinned": True})
        assert rejected.status_code == 422
        saved = client.put(f"/api/sessions/{session['id']}/summary", json={"summary": "- 故郷へ帰る"}).json()
        assert saved["adoptionSummary"] == "- 故郷へ帰る" and saved["status"] == "adopted"
        results = client.get("/api/search", params={"q": "故郷"}).json()
        assert any(result["sessionId"] == session["id"] for result in results)
    finally:
        app.dependency_overrides.clear()


def test_adopted_session_invariant_and_readoption(db):
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        project = client.post("/api/projects", json={"title": "P"}).json()
        thread = client.post(f"/api/projects/{project['id']}/threads", json={"title": "T"}).json()
        assert client.post(f"/api/threads/{thread['id']}/sessions", json={"title": "Invalid", "status": "adopted"}).status_code == 422
        session = client.post(f"/api/threads/{thread['id']}/sessions", json={"title": "S"}).json()

        assert client.patch(f"/api/sessions/{session['id']}", json={"status": "adopted"}).status_code == 422
        adopted = client.put(f"/api/sessions/{session['id']}/summary", json={"summary": "  決定事項  "}).json()
        assert adopted["status"] == "adopted"
        assert adopted["adoptionSummary"] == "決定事項"

        rejected = client.patch(f"/api/sessions/{session['id']}", json={"status": "rejected"}).json()
        assert rejected["adoptionSummary"] == "決定事項"
        readopted = client.patch(f"/api/sessions/{session['id']}", json={"status": "adopted"}).json()
        assert readopted["status"] == "adopted"
        assert readopted["adoptionSummary"] == "決定事項"

        assert client.patch(f"/api/sessions/{session['id']}", json={"adoptionSummary": "   "}).status_code == 422
        cleared = client.put(f"/api/sessions/{session['id']}/summary", json={"summary": "   "}).json()
        assert cleared["status"] == "considering"
        assert cleared["adoptionSummary"] is None
    finally:
        app.dependency_overrides.clear()


def test_message_search_returns_parent_ids(db):
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        project = client.post("/api/projects", json={"title": "P"}).json()
        thread = client.post(f"/api/projects/{project['id']}/threads", json={"title": "T"}).json()
        session = client.post(f"/api/threads/{thread['id']}/sessions", json={"title": "S"}).json()
        from app.models import Message
        message = Message(session_id=session["id"], role="user", content="固有の検索本文")
        db.add(message); db.commit()

        result = next(item for item in client.get("/api/search", params={"q": "固有"}).json() if item["type"] == "message")
        assert result["id"] == message.id
        assert result["projectId"] == project["id"]
        assert result["threadId"] == thread["id"]
        assert result["sessionId"] == session["id"]
    finally:
        app.dependency_overrides.clear()


def test_health_distinguishes_database_and_llm(db, monkeypatch):
    app.dependency_overrides[get_db] = lambda: db

    class Response:
        status_code = 200

    monkeypatch.setattr("httpx.get", lambda *args, **kwargs: Response())
    monkeypatch.setattr("app.api.llm.settings.openai_base_url", "http://llm.test/v1")
    monkeypatch.setattr("app.api.llm.settings.openai_model", "qwen-test")
    try:
        payload = TestClient(app).get("/api/health").json()
        assert payload == {"status": "ok", "database": "ok", "llm": "ok", "model": "qwen-test"}
    finally:
        app.dependency_overrides.clear()
