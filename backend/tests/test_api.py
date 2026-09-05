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
        updated = client.patch(f"/api/sessions/{session['id']}", json={"status": "adopted", "pinned": True}).json()
        assert updated["status"] == "adopted" and updated["pinned"] is True
        saved = client.put(f"/api/sessions/{session['id']}/summary", json={"summary": "- 故郷へ帰る"}).json()
        assert saved["adoptionSummary"] == "- 故郷へ帰る"
        results = client.get("/api/search", params={"q": "故郷"}).json()
        assert any(result["sessionId"] == session["id"] for result in results)
    finally:
        app.dependency_overrides.clear()
