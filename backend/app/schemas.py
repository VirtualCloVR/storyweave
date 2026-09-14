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

class FactIn(ApiModel):
    key: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=2000)
    sort_order: int = Field(default=0, ge=0, le=100_000)

class CharacterFactOut(FactIn):
    id: str
    character_id: str
    created_at: datetime
    updated_at: datetime

class CharacterCreate(ApiModel):
    name: str = Field(min_length=1, max_length=240)
    source_title: str | None = Field(default=None, max_length=500)
    aliases: list[str] = Field(default_factory=list, max_length=50)
    facts: list[FactIn] = Field(default_factory=list, max_length=200)

class CharacterUpdate(ApiModel):
    name: str | None = Field(default=None, min_length=1, max_length=240)
    source_title: str | None = Field(default=None, max_length=500)
    aliases: list[str] | None = Field(default=None, max_length=50)
    facts: list[FactIn] | None = Field(default=None, max_length=200)

class CharacterOut(ApiModel):
    id: str
    name: str
    source_title: str | None
    aliases: list[str]
    facts: list[CharacterFactOut]
    created_at: datetime
    updated_at: datetime

class ThreadCharacterIn(ApiModel):
    character_id: str
    always_include: bool = False
    sort_order: int = Field(default=0, ge=0, le=100_000)

class ThreadCharacterOut(ApiModel):
    character: CharacterOut
    always_include: bool
    sort_order: int

class ThreadSceneFactOut(FactIn):
    id: str
    thread_id: str
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

class ContextSessionOut(ApiModel):
    id: str
    title: str
    summary: str
    archived: bool

class ContextCharacterOut(ApiModel):
    id: str
    name: str
    included: bool
    reason: Literal["always_include", "mentioned"] | None = None
    facts: list[FactIn]

class ContextCanonOut(ApiModel):
    digest_status: Literal["fresh", "stale", "unused", "generated", "failed"]
    relevant_sessions: list[ContextSessionOut]

class ContextInspectorOut(ApiModel):
    project: ProjectOut
    thread: ThreadOut
    current_session: SessionOut
    adopted_sessions: list[ContextSessionOut]
    excluded_counts: dict[str, int]
    confirmed_context_chars: int
    current_history_chars: int
    budget_chars: int
    total_chars: int
    mode: Literal["full", "digest"]
    characters: list[ContextCharacterOut]
    scene_facts: list[FactIn]
    canon: ContextCanonOut
    sizes: dict[str, int]
    compression_degraded: bool

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

class ContextPreviewIn(ApiModel):
    content: str = Field(min_length=1, max_length=20_000)

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
