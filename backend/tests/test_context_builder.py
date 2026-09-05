from datetime import datetime, timedelta, timezone
import pytest
from app.context_builder import adopted_sessions_for_context, build_confirmed_context, build_system_context
from app.models import Project, StorySession, Thread

def make_tree(db):
    project = Project(title="Project A")
    thread = Thread(title="Thread A", project=project)
    current = StorySession(title="Current", thread=thread, status="considering")
    db.add(project); db.commit()
    return project, thread, current

def add_session(db, thread, title, status, summary=None, archived=False, created_at=None):
    item = StorySession(thread=thread, title=title, status=status, adoption_summary=summary, archived=archived)
    if created_at:
        item.created_at = created_at
    db.add(item); db.commit()
    return item

def test_same_thread_adopted_is_included(db):
    _, thread, current = make_tree(db)
    add_session(db, thread, "事故要素", "adopted", "- 自転車事故")
    assert "[事故要素]\n- 自転車事故" in build_confirmed_context(db, current)

@pytest.mark.parametrize("status", ["considering", "rejected", "superseded"])
def test_non_adopted_status_is_excluded(db, status):
    _, thread, current = make_tree(db)
    add_session(db, thread, f"{status}案", status, "SHOULD_NOT_APPEAR")
    assert "SHOULD_NOT_APPEAR" not in build_confirmed_context(db, current)

def test_other_thread_adopted_is_excluded(db):
    project, _, current = make_tree(db)
    other = Thread(title="Other Thread", project=project); db.add(other); db.commit()
    add_session(db, other, "別作品", "adopted", "OTHER_THREAD")
    assert "OTHER_THREAD" not in build_confirmed_context(db, current)

def test_other_project_adopted_is_excluded(db):
    _, _, current = make_tree(db)
    project = Project(title="Project B"); thread = Thread(title="Thread B", project=project)
    db.add(project); db.commit(); add_session(db, thread, "別企画", "adopted", "OTHER_PROJECT")
    assert "OTHER_PROJECT" not in build_confirmed_context(db, current)

def test_archived_adopted_is_included(db):
    _, thread, current = make_tree(db)
    add_session(db, thread, "完了議論", "adopted", "ARCHIVED_CONFIRMED", archived=True)
    assert "ARCHIVED_CONFIRMED" in build_confirmed_context(db, current)

def test_current_session_never_duplicates_itself(db):
    _, _, current = make_tree(db)
    current.status = "adopted"; current.adoption_summary = "CURRENT_SUMMARY"; db.commit()
    assert "CURRENT_SUMMARY" not in build_confirmed_context(db, current)

def test_status_change_removes_summary(db):
    _, thread, current = make_tree(db)
    adopted = add_session(db, thread, "確定案", "adopted", "ONCE_CONFIRMED")
    assert "ONCE_CONFIRMED" in build_confirmed_context(db, current)
    adopted.status = "superseded"; db.commit()
    assert "ONCE_CONFIRMED" not in build_confirmed_context(db, current)
    assert adopted.adoption_summary == "ONCE_CONFIRMED"

def test_multiple_adopted_sessions_have_stable_order(db):
    _, thread, current = make_tree(db)
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    second = add_session(db, thread, "Second", "adopted", "B", created_at=base + timedelta(days=1))
    first = add_session(db, thread, "First", "adopted", "A", created_at=base)
    assert [item.id for item in adopted_sessions_for_context(db, current)] == [first.id, second.id]
    assert build_confirmed_context(db, current).index("[First]") < build_confirmed_context(db, current).index("[Second]")

def test_system_context_contains_hierarchy_and_confirmed_only(db):
    project, thread, current = make_tree(db)
    add_session(db, thread, "採用", "adopted", "YES")
    add_session(db, thread, "検討", "considering", "NO")
    context = build_system_context(db, current)
    assert project.title in context and thread.title in context and current.title in context
    assert "CONFIRMED CONTEXT" in context and "YES" in context and "NO" not in context

