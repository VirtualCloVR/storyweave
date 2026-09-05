import enum
import uuid
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

def new_id() -> str:
    return str(uuid.uuid4())

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

class SessionStatus(str, enum.Enum):
    considering = "considering"
    adopted = "adopted"
    rejected = "rejected"
    superseded = "superseded"

class MessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"
    system = "system"
    tool = "tool"

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

class Project(TimestampMixin, Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str | None] = mapped_column(Text)
    system_prompt: Mapped[str | None] = mapped_column(Text)
    threads: Mapped[list["Thread"]] = relationship(back_populates="project", cascade="all, delete-orphan")

class Thread(TimestampMixin, Base):
    __tablename__ = "threads"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str | None] = mapped_column(Text)
    project: Mapped[Project] = relationship(back_populates="threads")
    sessions: Mapped[list["StorySession"]] = relationship(back_populates="thread", cascade="all, delete-orphan")

class StorySession(TimestampMixin, Base):
    __tablename__ = "sessions"
    __table_args__ = (CheckConstraint("status IN ('considering','adopted','rejected','superseded')", name="ck_session_status"), CheckConstraint("status != 'adopted' OR (adoption_summary IS NOT NULL AND length(trim(adoption_summary)) > 0)", name="ck_adopted_requires_summary"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    thread_id: Mapped[str] = mapped_column(ForeignKey("threads.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(240))
    status: Mapped[SessionStatus] = mapped_column(String(20), default=SessionStatus.considering)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    adoption_summary: Mapped[str | None] = mapped_column(Text)
    thread: Mapped[Thread] = relationship(back_populates="sessions")
    messages: Mapped[list["Message"]] = relationship(back_populates="session", cascade="all, delete-orphan", order_by="Message.created_at")
    sources: Mapped[list["Source"]] = relationship(back_populates="session", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (CheckConstraint("role IN ('user','assistant','system','tool')", name="ck_message_role"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    role: Mapped[MessageRole] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(String(240))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    session: Mapped[StorySession] = relationship(back_populates="messages")

class Source(Base):
    __tablename__ = "sources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    message_id: Mapped[str | None] = mapped_column(ForeignKey("messages.id", ondelete="SET NULL"))
    url: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(20), default="fetch")
    provider: Mapped[str | None] = mapped_column(String(80))
    query: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(String(500))
    excerpt: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    session: Mapped[StorySession] = relationship(back_populates="sources")
