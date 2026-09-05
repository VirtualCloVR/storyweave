from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field
from .models import MessageRole, SessionStatus

def camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)

class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=camel)

class ProjectCreate(ApiModel):
    title: str = Field(min_length=1, max_length=240)
    description: str | None = None
    system_prompt: str | None = None

class ProjectUpdate(ApiModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = None
    system_prompt: str | None = None

class ProjectOut(ProjectCreate):
    id: str
    created_at: datetime
    updated_at: datetime

class ThreadCreate(ApiModel):
    title: str = Field(min_length=1, max_length=240)
    description: str | None = None

class ThreadUpdate(ApiModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = None

class ThreadOut(ThreadCreate):
    id: str
    project_id: str
    created_at: datetime
    updated_at: datetime

class SessionCreate(ApiModel):
    title: str = Field(min_length=1, max_length=240)
    status: SessionStatus = SessionStatus.considering
    archived: bool = False
    pinned: bool = False

class SessionUpdate(ApiModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    status: SessionStatus | None = None
    archived: bool | None = None
    pinned: bool | None = None
    adoption_summary: str | None = None

class SessionOut(ApiModel):
    id: str
    thread_id: str
    title: str
    status: SessionStatus
    archived: bool
    pinned: bool
    adoption_summary: str | None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

class MessageCreate(ApiModel):
    role: MessageRole
    content: str = Field(min_length=1)
    model: str | None = None
    metadata_json: dict[str, Any] | None = None

class MessageOut(MessageCreate):
    id: str
    session_id: str
    created_at: datetime

class ChatIn(ApiModel):
    content: str = Field(min_length=1)
    web_search_queries: list[str] = Field(default_factory=list, max_length=5)
    fetch_urls: list[str] = Field(default_factory=list, max_length=5)

class SummaryIn(ApiModel):
    summary: str

class SummaryOut(ApiModel):
    summary: str

class SourceCreate(ApiModel):
    url: str
    source_type: Literal["search", "fetch"] = "fetch"
    provider: str | None = None
    query: str | None = None
    title: str | None = None
    excerpt: str | None = None
    message_id: str | None = None

class SourceOut(SourceCreate):
    id: str
    session_id: str
    fetched_at: datetime

class MessageWithSourcesOut(MessageOut):
    sources: list[SourceOut] = Field(default_factory=list)

class WebSearchIn(ApiModel):
    query: str = Field(min_length=1, max_length=500)

class WebFetchIn(ApiModel):
    url: str = Field(min_length=1, max_length=4000)

class SearchResult(ApiModel):
    id: str
    type: Literal["project", "thread", "session", "message"]
    title: str
    excerpt: str | None = None
    project_id: str | None = None
    thread_id: str | None = None
    session_id: str | None = None
    status: SessionStatus | None = None
    archived: bool | None = None
