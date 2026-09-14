"""Regression coverage for Storyweave v0.2 structured context.

These tests intentionally exercise the public HTTP surface as well as the small,
deterministic planner helpers.  They use the in-memory fixture so they do not
depend on a running PostgreSQL or LLM service.
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import llm
from app.main import app
from app.config import settings
from app.context_planner import (
    build_context_plan,
    canon_source_hash,
    compact_facts,
    digest_freshness,
    normalize_text,
    relevant_adopted_sessions,
    serialize_character,
    serialize_scene,
)
from app.db import get_db
from app.models import (
    Character,
    CharacterFact,
    Message,
    Project,
    StorySession,
    Thread,
    ThreadCharacter,
    ThreadContextDigest,
    ThreadSceneFact,
)
from app.tools import FetchResult


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def tree(db, title="P"):
    project = Project(title=title, system_prompt="Use the canon faithfully.")
    thread = Thread(project=project, title="Thread")
    current = StorySession(thread=thread, title="Current", status="considering")
    db.add(project)
    db.commit()
    return project, thread, current


def adopted(db, thread, title, summary, *, archived=False):
    item = StorySession(thread=thread, title=title, status="adopted", adoption_summary=summary, archived=archived)
    db.add(item)
    db.commit()
    return item


def test_character_crud_replaces_facts_transactionally_and_normalizes_input(client):
    response = client.post("/api/characters", json={
        "name": "  千早愛音 ", "sourceTitle": "  MyGO  ",
        "aliases": [" 愛音 ", "愛音", "", "あのんちゃん"],
        "facts": [{"key": " 身長 ", "value": " 160cm ", "sortOrder": 2}],
    })
    assert response.status_code == 201
    character = response.json()
    assert character["name"] == "千早愛音"
    assert character["sourceTitle"] == "MyGO"
    assert character["aliases"] == ["愛音", "あのんちゃん"]
    assert character["facts"][0]["key"] == "身長"

    replaced = client.patch(f"/api/characters/{character['id']}", json={
        "facts": [{"key": "誕生日", "value": "9/8"}],
    })
    assert replaced.status_code == 200
    assert [(f["key"], f["value"]) for f in replaced.json()["facts"]] == [("誕生日", "9/8")]

    too_long = client.post("/api/characters", json={"name": "x", "facts": [{"key": "k", "value": "v" * 2001}]})
    assert too_long.status_code == 422
    too_many = client.post("/api/characters", json={"name": "x", "aliases": [str(i) for i in range(51)]})
    assert too_many.status_code == 422


def test_cast_replace_is_atomic_and_validates_duplicates(client, db):
    _, thread, _ = tree(db)
    chars = [client.post("/api/characters", json={"name": name}).json() for name in ("A", "B")]
    assert client.put(f"/api/threads/{thread.id}/characters", json=[{"characterId": chars[0]["id"], "alwaysInclude": True}]).status_code == 200
    bad = client.put(f"/api/threads/{thread.id}/characters", json=[
        {"characterId": chars[0]["id"]}, {"characterId": chars[0]["id"]},
    ])
    assert bad.status_code == 422
    # The failed replacement did not erase the previous cast.
    assert [row["character"]["name"] for row in client.get(f"/api/threads/{thread.id}/characters").json()] == ["A"]
    missing = client.put(f"/api/threads/{thread.id}/characters", json=[{"characterId": "missing"}])
    assert missing.status_code == 422
    assert [row["character"]["name"] for row in client.get(f"/api/threads/{thread.id}/characters").json()] == ["A"]


def test_scene_facts_are_thread_local_and_replaced(client, db):
    project, thread_a, _ = tree(db)
    thread_b = Thread(project=project, title="Other")
    db.add(thread_b); db.commit()
    assert client.put(f"/api/threads/{thread_a.id}/scene-facts", json=[{"key": "舞台", "value": "無人島"}]).status_code == 200
    assert client.put(f"/api/threads/{thread_b.id}/scene-facts", json=[{"key": "舞台", "value": "箱根"}]).status_code == 200
    assert client.get(f"/api/threads/{thread_a.id}/scene-facts").json()[0]["value"] == "無人島"
    assert client.get(f"/api/threads/{thread_b.id}/scene-facts").json()[0]["value"] == "箱根"


def test_normalization_alias_and_recent_user_mentions(db):
    _, thread, current = tree(db)
    char = Character(name="Alice", aliases=["Ａｌｉｃｅ", "アリス"])
    char.facts = [CharacterFact(key="role", value="hero", sort_order=0)]
    db.add(char); db.flush()
    db.add(ThreadCharacter(thread_id=thread.id, character_id=char.id, always_include=False))
    old = Message(session_id=current.id, role="user", content="アリスについて")
    recent = Message(session_id=current.id, role="user", content="ＡＬＩＣＥの場面")
    db.add_all([old, recent]); db.commit()
    plan = asyncio_run(build_context_plan(db, current, "続き", [old, recent]))
    assert plan.characters[0].included and plan.characters[0].reason == "mentioned"
    assert normalize_text("Ａlice") == normalize_text("alice")


def test_unlinked_global_character_is_never_a_context_candidate(db):
    _, thread, current = tree(db)
    linked = Character(name="Linked", aliases=[], facts=[CharacterFact(key="role", value="friend", sort_order=0)])
    unlinked = Character(name="SecretName", aliases=["秘密"], facts=[CharacterFact(key="secret", value="MUST_NOT_LEAK", sort_order=0)])
    db.add_all([linked, unlinked]); db.flush()
    db.add(ThreadCharacter(thread_id=thread.id, character_id=linked.id, always_include=False))
    db.commit()
    plan = asyncio_run(build_context_plan(db, current, "SecretNameと秘密について", []))
    assert [item.name for item in plan.characters] == ["Linked"]
    assert "MUST_NOT_LEAK" not in plan.system_text


def test_global_character_is_reused_by_reference_and_edits_reach_both_threads(client, db):
    project, thread_a, current_a = tree(db)
    thread_b = Thread(project=project, title="Thread B")
    current_b = StorySession(thread=thread_b, title="Current B", status="considering")
    db.add(thread_b); db.commit()
    char = client.post("/api/characters", json={"name": "愛音", "facts": [{"key": "身長", "value": "160cm"}]}).json()
    for thread in (thread_a, thread_b):
        assert client.put(f"/api/threads/{thread.id}/characters", json=[{"characterId": char["id"], "alwaysInclude": True}]).status_code == 200
    client.patch(f"/api/characters/{char['id']}", json={"facts": [{"key": "身長", "value": "161cm"}]})
    plan_a = asyncio_run(build_context_plan(db, current_a, "", []))
    plan_b = asyncio_run(build_context_plan(db, current_b, "", []))
    assert "身長=161cm" in plan_a.character_text
    assert "身長=161cm" in plan_b.character_text
    assert db.query(CharacterFact).filter(CharacterFact.character_id == char["id"]).count() == 1


def asyncio_run(awaitable):
    import asyncio
    return asyncio.run(awaitable)


def test_compact_serialization_escapes_delimiters_and_orders_facts():
    assert compact_facts([("b|", "line\n2", 2), ("a=", "x\\y", 1)]) == "a\\==x\\\\y | b\\|=line\\n2"
    assert serialize_character("A|", [("k", "v", 0)]) == "[CHARACTER A\\|]\nk=v"
    assert serialize_scene([]) == ""


def test_adopted_scope_archive_and_other_thread_exclusion(db):
    project, thread, current = tree(db)
    other = Thread(project=project, title="Other")
    db.add(other); db.commit()
    included = adopted(db, thread, "Archived", "ARCHIVED", archived=True)
    adopted(db, other, "Foreign", "FOREIGN")
    plan = asyncio_run(build_context_plan(db, current, "", []))
    assert [item.id for item in plan.adopted_sessions] == [included.id]
    assert "ARCHIVED" in plan.canon_text and "FOREIGN" not in plan.canon_text


def test_relevant_selection_prefers_matching_canon():
    a = StorySession(id="a", title="海辺", status="adopted", adoption_summary="夏の海辺で花火")
    b = StorySession(id="b", title="山", status="adopted", adoption_summary="冬の山小屋")
    assert [item.id for item in relevant_adopted_sessions([a, b], "海辺の花火")] == ["a"]


def test_digest_source_hash_freshness_and_stale(db):
    _, thread, _ = tree(db)
    item = adopted(db, thread, "Canon", "one")
    source_hash = canon_source_hash([item])
    digest = ThreadContextDigest(thread_id=thread.id, content="one", source_hash=source_hash, source_session_count=1, source_chars=3)
    db.add(digest); db.commit()
    assert digest_freshness(digest, source_hash) == "fresh"
    item.adoption_summary = "changed"; db.commit()
    assert digest_freshness(digest, canon_source_hash([item])) == "stale"


def test_fresh_digest_is_reused_and_changed_canon_regenerates(db, monkeypatch):
    _, thread, current = tree(db)
    item = adopted(db, thread, "Long Canon", "A" * 1200)
    monkeypatch.setattr(settings, "context_budget_chars", 500)
    monkeypatch.setattr(settings, "context_digest_target_chars", 100)
    calls = []

    async def generate(items, target):
        calls.append((canon_source_hash(items), target))
        return "compact canon"

    first = asyncio_run(build_context_plan(db, current, "zz", [], digest_generator=generate))
    second = asyncio_run(build_context_plan(db, current, "zz", [], digest_generator=generate))
    assert first.digest_status == "generated"
    assert second.digest_status == "fresh"
    assert len(calls) == 1
    item.adoption_summary = "B" * 1200
    db.commit()
    third = asyncio_run(build_context_plan(db, current, "zz", [], digest_generator=generate))
    assert third.digest_status == "generated"
    assert len(calls) == 2


def test_planner_full_mode_includes_character_scene_and_web(db, monkeypatch):
    _, thread, current = tree(db)
    char = Character(name="A", aliases=["エー"], facts=[CharacterFact(key="色", value="赤", sort_order=0)])
    db.add(char); db.flush()
    db.add(ThreadCharacter(thread_id=thread.id, character_id=char.id, always_include=True))
    db.add(ThreadSceneFact(thread_id=thread.id, key="季節", value="夏", sort_order=0)); db.commit()
    monkeypatch.setattr(settings, "context_budget_chars", 20_000)
    source = FetchResult(url="https://example.test", title="Source", text="web fact", source_type="fetch")
    plan = asyncio_run(build_context_plan(db, current, "質問", [], [source]))
    assert plan.compression_mode == "full"
    assert "[CHARACTER A]" in plan.system_text and "色=赤" in plan.character_text
    assert "季節=夏" in plan.scene_text and "web fact" in plan.web_text


def test_planner_digest_and_fallback_degraded(monkeypatch, db):
    _, thread, current = tree(db)
    adopted(db, thread, "One", "alpha " * 30)
    adopted(db, thread, "Two", "beta " * 30)
    monkeypatch.setattr(settings, "context_budget_chars", 450)
    monkeypatch.setattr(settings, "context_digest_target_chars", 40)

    async def fail(items, target):
        raise RuntimeError("digest unavailable")

    plan = asyncio_run(build_context_plan(db, current, "alpha", [], digest_generator=fail))
    assert plan.compression_mode == "digest"
    assert plan.digest_status == "failed"
    assert plan.compression_degraded is True
    assert "CONTEXT WARNING" in plan.system_text
    assert plan.total_chars <= settings.context_budget_chars


def test_inspector_and_preview_expose_structured_context(client, db):
    _, thread, current = tree(db)
    char = client.post("/api/characters", json={"name": "愛音", "facts": [{"key": "学年", "value": "1年"}]}).json()
    client.put(f"/api/threads/{thread.id}/characters", json=[{"characterId": char["id"], "alwaysInclude": True}])
    client.put(f"/api/threads/{thread.id}/scene-facts", json=[{"key": "場所", "value": "東京"}])
    db.add(Message(session_id=current.id, role="user", content="こんにちは")); db.commit()
    inspector = client.get(f"/api/sessions/{current.id}/context").json()
    preview = client.post(f"/api/sessions/{current.id}/context/preview", json={"content": "愛音の話"}).json()
    assert inspector["characters"][0]["included"] is True
    assert inspector["sceneFacts"][0]["value"] == "東京"
    assert preview["currentSession"]["id"] == current.id


def test_web_source_context_is_budgeted(db, monkeypatch):
    _, thread, current = tree(db)
    monkeypatch.setattr(settings, "context_budget_chars", 700)
    monkeypatch.setattr(settings, "context_web_max_chars", 400)
    source = FetchResult(url="https://example.test", title="T", text="x" * 500, source_type="fetch")
    plan = asyncio_run(build_context_plan(db, current, "q", [], [source]))
    assert len(plan.web_text) <= 400
    assert "UNTRUSTED WEB SOURCE BEGIN" in plan.web_text
    assert plan.web_text.endswith("UNTRUSTED WEB SOURCE END")
    assert plan.total_chars <= settings.context_budget_chars


def test_chat_prompt_contains_character_scene_and_canon(client, db, monkeypatch):
    _, thread, current = tree(db)
    char = client.post("/api/characters", json={"name": "愛音", "facts": [{"key": "役割", "value": "主人公"}]}).json()
    client.put(f"/api/threads/{thread.id}/characters", json=[{"characterId": char["id"], "alwaysInclude": True}])
    client.put(f"/api/threads/{thread.id}/scene-facts", json=[{"key": "舞台", "value": "東京"}])
    adopted(db, thread, "Canon", "二人は友人")
    captured = {}

    async def fake_stream(prompt):
        captured["prompt"] = prompt
        yield "ok"

    monkeypatch.setattr(llm, "stream_completion", fake_stream)
    response = client.post(f"/api/sessions/{current.id}/chat", json={"content": "愛音について"})
    assert response.status_code == 200
    body = response.text
    assert "[CHARACTER 愛音]" in captured["prompt"][0]["content"]
    assert "舞台=東京" in captured["prompt"][0]["content"]
    assert "二人は友人" in captured["prompt"][0]["content"]
    assert "ok" in body
