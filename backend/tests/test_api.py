from fastapi.testclient import TestClient
from app.models import Character, CharacterFact, Message, Project, Source, StorySession, Thread, ThreadCharacter, ThreadContextDigest, ThreadSceneFact
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


def test_creating_threads_preserves_existing_threads_and_sessions(db):
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        project = client.post("/api/projects", json={"title": "Thread regression"}).json()
        path = f"/api/projects/{project['id']}/threads"
        first = client.post(path, json={"title": "First"}).json()
        session = client.post(f"/api/threads/{first['id']}/sessions", json={"title": "Existing session"}).json()
        client.put(f"/api/sessions/{session['id']}/summary", json={"summary": "Keep existing canon"})
        created = [first]
        for title in ("Second", "Third"):
            response = client.post(path, json={"title": title})
            assert response.status_code == 201
            created.append(response.json())
            assert {row["id"] for row in client.get(path).json()} == {row["id"] for row in created}
        db.expire_all()
        assert len({row["id"] for row in created}) == 3
        assert client.get(f"/api/threads/{first['id']}").json() == first
        saved = client.get(f"/api/threads/{first['id']}/sessions").json()
        assert len(saved) == 1
        assert saved[0]["id"] == session["id"]
        assert saved[0]["adoptionSummary"] == "Keep existing canon"
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


def test_delete_project_cascades_owned_tree_but_preserves_unrelated_data(db):
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        doomed_project = client.post("/api/projects", json={"title": "Delete me"}).json()
        kept_project = client.post("/api/projects", json={"title": "Keep me"}).json()
        doomed_thread = client.post(f"/api/projects/{doomed_project['id']}/threads", json={"title": "Owned thread"}).json()
        kept_thread = client.post(f"/api/projects/{kept_project['id']}/threads", json={"title": "Unrelated thread"}).json()
        doomed_session = client.post(f"/api/threads/{doomed_thread['id']}/sessions", json={"title": "Owned session"}).json()
        kept_session = client.post(f"/api/threads/{kept_thread['id']}/sessions", json={"title": "Unrelated session"}).json()
        character = client.post("/api/characters", json={"name": "Global character", "facts": [{"key": "role", "value": "survivor"}]}).json()
        client.put(f"/api/threads/{doomed_thread['id']}/characters", json=[{"character_id": character["id"], "always_include": True}])
        client.put(f"/api/threads/{doomed_thread['id']}/scene-facts", json=[{"key": "weather", "value": "rain"}])

        doomed_message = Message(session_id=doomed_session["id"], role="user", content="owned message")
        kept_message = Message(session_id=kept_session["id"], role="user", content="kept message")
        db.add_all([doomed_message, kept_message]); db.flush()
        db.add(Source(session_id=doomed_session["id"], message_id=doomed_message.id, url="https://owned.test"))
        db.add(ThreadContextDigest(thread_id=doomed_thread["id"], content="old digest", source_hash="a" * 64, source_session_count=1, source_chars=5))
        db.commit()

        response = client.delete(f"/api/projects/{doomed_project['id']}")
        assert response.status_code == 204
        assert db.get(Thread, doomed_thread["id"]) is None
        assert db.get(StorySession, doomed_session["id"]) is None
        assert db.get(Message, doomed_message.id) is None
        assert db.scalar(Source.__table__.select().where(Source.session_id == doomed_session["id"])) is None
        assert db.get(ThreadCharacter, (doomed_thread["id"], character["id"])) is None
        assert db.scalar(ThreadSceneFact.__table__.select().where(ThreadSceneFact.thread_id == doomed_thread["id"])) is None
        assert db.get(ThreadContextDigest, doomed_thread["id"]) is None
        assert db.get(Character, character["id"]) is not None
        assert db.get(CharacterFact, character["facts"][0]["id"]) is not None
        assert db.get(Project, kept_project["id"]) is not None
        assert db.get(Thread, kept_thread["id"]) is not None
        assert db.get(StorySession, kept_session["id"]) is not None
        assert db.get(Message, kept_message.id) is not None
    finally:
        app.dependency_overrides.clear()


def test_delete_adopted_session_cascades_children_and_invalidates_digest(db):
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        project = client.post("/api/projects", json={"title": "P"}).json()
        thread = client.post(f"/api/projects/{project['id']}/threads", json={"title": "T"}).json()
        adopted = client.post(f"/api/threads/{thread['id']}/sessions", json={"title": "Adopted"}).json()
        kept = client.post(f"/api/threads/{thread['id']}/sessions", json={"title": "Kept"}).json()
        client.put(f"/api/sessions/{adopted['id']}/summary", json={"summary": "Keep this canon"})
        message = Message(session_id=adopted["id"], role="user", content="old")
        db.add(message); db.flush()
        db.add(Source(session_id=adopted["id"], message_id=message.id, url="https://source.test"))
        db.add(ThreadContextDigest(thread_id=thread["id"], content="digest", source_hash="b" * 64, source_session_count=1, source_chars=4))
        db.commit()

        assert client.delete(f"/api/sessions/{adopted['id']}").status_code == 204
        assert db.get(StorySession, adopted["id"]) is None
        assert db.get(Message, message.id) is None
        assert db.scalar(Source.__table__.select().where(Source.session_id == adopted["id"])) is None
        assert db.get(ThreadContextDigest, thread["id"]) is None
        assert db.get(StorySession, kept["id"]) is not None
    finally:
        app.dependency_overrides.clear()


def test_delete_thread_preserves_project_and_other_thread(db):
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        project = client.post("/api/projects", json={"title": "Keep project"}).json()
        doomed = client.post(f"/api/projects/{project['id']}/threads", json={"title": "Delete thread"}).json()
        kept = client.post(f"/api/projects/{project['id']}/threads", json={"title": "Keep thread"}).json()
        doomed_session = client.post(f"/api/threads/{doomed['id']}/sessions", json={"title": "Owned"}).json()
        kept_session = client.post(f"/api/threads/{kept['id']}/sessions", json={"title": "Unrelated"}).json()

        assert client.delete(f"/api/threads/{doomed['id']}").status_code == 204
        assert db.get(Project, project["id"]) is not None
        assert db.get(Thread, doomed["id"]) is None
        assert db.get(StorySession, doomed_session["id"]) is None
        assert db.get(Thread, kept["id"]) is not None
        assert db.get(StorySession, kept_session["id"]) is not None
    finally:
        app.dependency_overrides.clear()
