"""Run a small live-stack smoke test without leaving test data behind."""
import os
import httpx

api = os.getenv("STORYWEAVE_API", "http://localhost:8000/api").rstrip("/")
frontend = os.getenv("STORYWEAVE_FRONTEND", "http://localhost:5173")

with httpx.Client(timeout=10) as client:
    project_id = None
    try:
        assert client.get(f"{api}/health").json() == {"status": "ok"}
        page = client.get(frontend)
        assert page.status_code == 200 and "storyweave" in page.text.lower()

        project = client.post(f"{api}/projects", json={"title": "WSL smoke test"}).raise_for_status().json()
        project_id = project["id"]
        thread = client.post(f"{api}/projects/{project_id}/threads", json={"title": "API integration"}).raise_for_status().json()
        session = client.post(f"{api}/threads/{thread['id']}/sessions", json={"title": "Knowledge inheritance"}).raise_for_status().json()
        updated = client.patch(f"{api}/sessions/{session['id']}", json={"status": "adopted", "pinned": True}).raise_for_status().json()
        assert updated["status"] == "adopted" and updated["pinned"] is True
        saved = client.put(f"{api}/sessions/{session['id']}/summary", json={"summary": "- WSLから保存を確認"}).raise_for_status().json()
        assert saved["adoptionSummary"] == "- WSLから保存を確認"
        results = client.get(f"{api}/search", params={"q": "WSLから保存"}).raise_for_status().json()
        assert any(item.get("sessionId") == session["id"] for item in results)
        print("smoke: health, frontend, CRUD, status, summary, and search passed")
    finally:
        if project_id:
            client.delete(f"{api}/projects/{project_id}").raise_for_status()
