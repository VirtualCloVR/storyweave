from sqlalchemy import func, select
from sqlalchemy.orm import Session
from .models import Project, StorySession, Thread

DEFAULT_SYSTEM_PROMPT = (
    "あなたは創作・ショートストーリー相談のアシスタントです。"
    "ユーザーが確定した設定と検討中の案を区別し、確定済みの文脈と矛盾しないよう支援してください。"
)

def adopted_sessions_for_context(db: Session, current: StorySession) -> list[StorySession]:
    """Return only confirmed sibling knowledge in a stable chronological order."""
    return list(db.scalars(
        select(StorySession)
        .where(
            StorySession.thread_id == current.thread_id,
            StorySession.id != current.id,
            StorySession.status == "adopted",
            func.trim(StorySession.adoption_summary) != "",
        )
        .order_by(StorySession.created_at.asc(), StorySession.id.asc())
    ))

def build_confirmed_context(db: Session, current: StorySession) -> str:
    items = adopted_sessions_for_context(db, current)
    if not items:
        return "（採用済みの確定事項はまだありません）"
    return "\n\n".join(f"[{item.title}]\n{item.adoption_summary.strip()}" for item in items if item.adoption_summary and item.adoption_summary.strip())

def build_system_context(db: Session, current: StorySession) -> str:
    thread = db.get(Thread, current.thread_id)
    if thread is None:
        raise ValueError("Session is not attached to a thread")
    project = db.get(Project, thread.project_id)
    if project is None:
        raise ValueError("Thread is not attached to a project")
    instruction = project.system_prompt.strip() if project.system_prompt else DEFAULT_SYSTEM_PROMPT
    return (
        f"SYSTEM\n{instruction}\n\n"
        f"PROJECT\n{project.title}\n\n"
        f"THREAD\n{thread.title}\n\n"
        f"CONFIRMED CONTEXT\n{build_confirmed_context(db, current)}\n\n"
        f"CURRENT SESSION\n{current.title}"
    )
