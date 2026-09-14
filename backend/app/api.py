import json
import logging
import re
from collections.abc import AsyncIterator
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session, joinedload, selectinload, sessionmaker
from . import llm
from .context_builder import adopted_sessions_for_context
from .context_planner import ContextPlan, build_context_plan
from .db import get_db
from .models import Character, CharacterFact, Message, Project, Source, StorySession, Thread, ThreadCharacter, ThreadContextDigest, ThreadSceneFact
from .schemas import (
    CharacterCreate, CharacterFactOut, CharacterOut, CharacterUpdate, ChatIn, ContextCharacterOut,
    ContextPreviewIn, FactIn, MessageOut, MessageWithSourcesOut, ProjectCreate, ProjectOut, ProjectUpdate, SearchResult,
    SessionCreate, SessionOut, SessionUpdate, SourceCreate, SourceOut, SummaryIn,
    SummaryOut, ThreadCharacterIn, ThreadCharacterOut, ThreadCreate, ThreadOut, ThreadSceneFactOut, ThreadUpdate,
    WebFetchIn, WebSearchIn, ContextCanonOut, ContextInspectorOut, ContextSessionOut,
)
from .tools import FetchResult
from .web import fetch_one, format_source_context, persist_source, search_and_fetch

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)

WEB_SEARCH_REQUEST = re.compile(
    r"(?:(?:web|ウェブ|ネット|インターネット).{0,12}(?:検索|調べ|探して|参照)|"
    r"(?:検索|調べ|探して).{0,12}(?:web|ウェブ|ネット|インターネット)|"
    r"(?:最新|直近|ニュース|公式情報|統計|ランキング|法律|法令).{0,40}(?:調べ|検索|確認|教えて))",
    re.IGNORECASE,
)
URL_PATTERN = re.compile(r"https?://[^\s<>\]\[()]+", re.IGNORECASE)

def require(db: Session, model: type, item_id: str):
    item = db.get(model, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
    return item

def apply_patch(item, payload) -> None:
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)

def validate_session_state(status: object, adoption_summary: str | None) -> None:
    if status == "adopted" and not (adoption_summary and adoption_summary.strip()):
        raise HTTPException(status_code=422, detail="adopted sessions require a non-empty adoption_summary")

def session_out(db: Session, item: StorySession) -> SessionOut:
    count = db.scalar(select(func.count(Message.id)).where(Message.session_id == item.id)) or 0
    return SessionOut.model_validate(item).model_copy(update={"message_count": count})

def message_out(db: Session, item: Message) -> MessageWithSourcesOut:
    sources = list(db.scalars(
        select(Source).where(Source.message_id == item.id).order_by(Source.fetched_at.asc(), Source.id.asc())
    ))
    return MessageWithSourcesOut.model_validate(item).model_copy(
        update={"sources": [SourceOut.model_validate(source) for source in sources]}
    )

def recent_history(items: list[Message], max_chars: int = 20_000) -> list[Message]:
    selected: list[Message] = []
    used = 0
    for item in reversed(items):
        size = len(item.content)
        if selected and used + size > max_chars:
            break
        selected.append(item)
        used += size
    return list(reversed(selected))

def clean_character_values(payload: CharacterCreate | CharacterUpdate) -> dict:
    values = payload.model_dump(exclude_unset=True)
    if "name" in values:
        values["name"] = values["name"].strip()
        if not values["name"]:
            raise HTTPException(status_code=422, detail="Character name cannot be blank")
    if "source_title" in values and values["source_title"] is not None:
        values["source_title"] = values["source_title"].strip() or None
    if "aliases" in values and values["aliases"] is not None:
        aliases: list[str] = []
        for raw in values["aliases"]:
            alias = raw.strip()
            if not alias:
                continue
            if len(alias) > 120:
                raise HTTPException(status_code=422, detail="Character alias must be at most 120 characters")
            if alias not in aliases:
                aliases.append(alias)
        values["aliases"] = aliases
    return values

def clean_facts(facts: list[FactIn]) -> list[dict]:
    cleaned: list[dict] = []
    for index, fact in enumerate(facts):
        key, value = fact.key.strip(), fact.value.strip()
        if not key or not value:
            raise HTTPException(status_code=422, detail="Fact key and value cannot be blank")
        cleaned.append({"key": key, "value": value, "sort_order": fact.sort_order if "sort_order" in fact.model_fields_set else index})
    return cleaned

def character_out(item: Character) -> CharacterOut:
    return CharacterOut.model_validate(item)

def inspector_out(db: Session, current: StorySession, plan: ContextPlan, history: list[Message]) -> ContextInspectorOut:
    thread = require(db, Thread, current.thread_id)
    project = require(db, Project, thread.project_id)
    counts = {status: db.scalar(select(func.count(StorySession.id)).where(StorySession.thread_id == thread.id, StorySession.id != current.id, StorySession.status == status)) or 0 for status in ("considering", "rejected", "superseded")}
    adopted_out = [ContextSessionOut(id=item.id, title=item.title, summary=(item.adoption_summary or "").strip(), archived=item.archived) for item in plan.adopted_sessions]
    relevant_out = [ContextSessionOut(id=item.id, title=item.title, summary=(item.adoption_summary or "").strip(), archived=item.archived) for item in plan.relevant_sessions]
    characters = [ContextCharacterOut(id=item.id, name=item.name, included=item.included, reason=item.reason, facts=[FactIn(key=key, value=value, sort_order=order) for key, value, order in item.facts]) for item in plan.characters]
    return ContextInspectorOut(
        project=project, thread=thread, current_session=session_out(db, current), adopted_sessions=adopted_out,
        excluded_counts=counts, confirmed_context_chars=len(plan.canon_text), current_history_chars=sum(len(item.content) for item in history),
        budget_chars=plan.budget_chars, total_chars=plan.total_chars, mode=plan.compression_mode, characters=characters,
        scene_facts=[FactIn(key=key, value=value, sort_order=order) for key, value, order in plan.scene_facts],
        canon=ContextCanonOut(digest_status=plan.digest_status, relevant_sessions=relevant_out), sizes=plan.sizes,
        compression_degraded=plan.compression_degraded,
    )

@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1")); database = "ok"
    except Exception:
        database = "unavailable"
    llm_status = "unavailable"
    if llm.settings.openai_base_url and llm.settings.openai_model:
        try:
            import httpx
            response = httpx.get(f"{llm.settings.openai_base_url.rstrip('/')}/models", headers=llm._headers(), timeout=3)
            llm_status = "ok" if response.status_code < 400 else "unavailable"
        except Exception:
            pass
    return {"status": "ok" if database == "ok" else "degraded", "database": database, "llm": llm_status, "model": llm.settings.openai_model}

@router.get("/projects", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return db.scalars(select(Project).order_by(Project.updated_at.desc())).all()

@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    item = Project(**payload.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    return item

@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, db: Session = Depends(get_db)):
    return require(db, Project, project_id)

@router.patch("/projects/{project_id}", response_model=ProjectOut)
def update_project(project_id: str, payload: ProjectUpdate, db: Session = Depends(get_db)):
    item = require(db, Project, project_id); apply_patch(item, payload); db.commit(); db.refresh(item)
    return item

@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: str, db: Session = Depends(get_db)):
    db.delete(require(db, Project, project_id)); db.commit()
    return Response(status_code=204)

@router.get("/projects/{project_id}/threads", response_model=list[ThreadOut])
def list_threads(project_id: str, db: Session = Depends(get_db)):
    require(db, Project, project_id)
    return db.scalars(select(Thread).where(Thread.project_id == project_id).order_by(Thread.updated_at.desc())).all()

@router.post("/projects/{project_id}/threads", response_model=ThreadOut, status_code=201)
def create_thread(project_id: str, payload: ThreadCreate, db: Session = Depends(get_db)):
    require(db, Project, project_id)
    item = Thread(project_id=project_id, **payload.model_dump()); db.add(item); db.commit(); db.refresh(item)
    return item

@router.get("/threads/{thread_id}", response_model=ThreadOut)
def get_thread(thread_id: str, db: Session = Depends(get_db)):
    return require(db, Thread, thread_id)

@router.patch("/threads/{thread_id}", response_model=ThreadOut)
def update_thread(thread_id: str, payload: ThreadUpdate, db: Session = Depends(get_db)):
    item = require(db, Thread, thread_id); apply_patch(item, payload); db.commit(); db.refresh(item)
    return item

@router.delete("/threads/{thread_id}", status_code=204)
def delete_thread(thread_id: str, db: Session = Depends(get_db)):
    db.delete(require(db, Thread, thread_id)); db.commit()
    return Response(status_code=204)

@router.get("/characters", response_model=list[CharacterOut])
def list_characters(db: Session = Depends(get_db)):
    return list(db.scalars(select(Character).options(selectinload(Character.facts)).order_by(Character.updated_at.desc(), Character.name)))

@router.post("/characters", response_model=CharacterOut, status_code=201)
def create_character(payload: CharacterCreate, db: Session = Depends(get_db)):
    values = clean_character_values(payload)
    facts = clean_facts(payload.facts)
    values.pop("facts", None)
    item = Character(**values)
    item.facts = [CharacterFact(**fact) for fact in facts]
    db.add(item); db.commit(); db.refresh(item)
    return character_out(item)

@router.get("/characters/{character_id}", response_model=CharacterOut)
def get_character(character_id: str, db: Session = Depends(get_db)):
    item = db.scalar(select(Character).where(Character.id == character_id).options(selectinload(Character.facts)))
    if item is None:
        raise HTTPException(status_code=404, detail="Character not found")
    return character_out(item)

@router.patch("/characters/{character_id}", response_model=CharacterOut)
def update_character(character_id: str, payload: CharacterUpdate, db: Session = Depends(get_db)):
    item = require(db, Character, character_id)
    values = clean_character_values(payload)
    values.pop("facts", None)
    for key, value in values.items():
        setattr(item, key, value)
    if payload.facts is not None:
        facts = clean_facts(payload.facts)
        item.facts.clear()
        item.facts.extend(CharacterFact(**fact) for fact in facts)
    db.commit(); db.refresh(item)
    return character_out(item)

@router.delete("/characters/{character_id}", status_code=204)
def delete_character(character_id: str, db: Session = Depends(get_db)):
    db.delete(require(db, Character, character_id)); db.commit()
    return Response(status_code=204)

@router.get("/threads/{thread_id}/characters", response_model=list[ThreadCharacterOut])
def list_thread_characters(thread_id: str, db: Session = Depends(get_db)):
    require(db, Thread, thread_id)
    links = db.execute(select(ThreadCharacter).where(ThreadCharacter.thread_id == thread_id).options(joinedload(ThreadCharacter.character).joinedload(Character.facts)).order_by(ThreadCharacter.sort_order, ThreadCharacter.character_id)).unique().scalars()
    return [ThreadCharacterOut(character=character_out(link.character), always_include=link.always_include, sort_order=link.sort_order) for link in links]

@router.put("/threads/{thread_id}/characters", response_model=list[ThreadCharacterOut])
def replace_thread_characters(thread_id: str, payload: list[ThreadCharacterIn], db: Session = Depends(get_db)):
    require(db, Thread, thread_id)
    ids = [item.character_id for item in payload]
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=422, detail="Character can only appear once in a Thread Cast")
    found = set(db.scalars(select(Character.id).where(Character.id.in_(ids)))) if ids else set()
    if found != set(ids):
        raise HTTPException(status_code=422, detail="One or more Characters do not exist")
    for link in list(db.scalars(select(ThreadCharacter).where(ThreadCharacter.thread_id == thread_id))):
        db.delete(link)
    db.flush()
    db.add_all(ThreadCharacter(thread_id=thread_id, **item.model_dump()) for item in payload)
    db.commit()
    return list_thread_characters(thread_id, db)

@router.get("/threads/{thread_id}/scene-facts", response_model=list[ThreadSceneFactOut])
def list_scene_facts(thread_id: str, db: Session = Depends(get_db)):
    require(db, Thread, thread_id)
    return list(db.scalars(select(ThreadSceneFact).where(ThreadSceneFact.thread_id == thread_id).order_by(ThreadSceneFact.sort_order, ThreadSceneFact.id)))

@router.put("/threads/{thread_id}/scene-facts", response_model=list[ThreadSceneFactOut])
def replace_scene_facts(thread_id: str, payload: list[FactIn], db: Session = Depends(get_db)):
    require(db, Thread, thread_id)
    facts = clean_facts(payload)
    for fact in list(db.scalars(select(ThreadSceneFact).where(ThreadSceneFact.thread_id == thread_id))):
        db.delete(fact)
    db.flush()
    db.add_all(ThreadSceneFact(thread_id=thread_id, **fact) for fact in facts)
    db.commit()
    return list_scene_facts(thread_id, db)

@router.get("/threads/{thread_id}/sessions", response_model=list[SessionOut])
def list_sessions(thread_id: str, db: Session = Depends(get_db)):
    require(db, Thread, thread_id)
    items = db.scalars(select(StorySession).where(StorySession.thread_id == thread_id).order_by(StorySession.pinned.desc(), StorySession.updated_at.desc())).all()
    return [session_out(db, item) for item in items]

@router.post("/threads/{thread_id}/sessions", response_model=SessionOut, status_code=201)
def create_session(thread_id: str, payload: SessionCreate, db: Session = Depends(get_db)):
    require(db, Thread, thread_id)
    if payload.status == "adopted":
        raise HTTPException(status_code=422, detail="create the session first, then save a non-empty adoption summary")
    item = StorySession(thread_id=thread_id, **payload.model_dump()); db.add(item); db.commit(); db.refresh(item)
    return session_out(db, item)

@router.get("/sessions/{session_id}", response_model=SessionOut)
def get_session(session_id: str, db: Session = Depends(get_db)):
    return session_out(db, require(db, StorySession, session_id))

@router.patch("/sessions/{session_id}", response_model=SessionOut)
def update_session(session_id: str, payload: SessionUpdate, db: Session = Depends(get_db)):
    item = require(db, StorySession, session_id)
    changes = payload.model_dump(exclude_unset=True)
    if "adoption_summary" in changes:
        changes["adoption_summary"] = changes["adoption_summary"].strip() or None if changes["adoption_summary"] is not None else None
    validate_session_state(changes.get("status", item.status), changes.get("adoption_summary", item.adoption_summary))
    for key, value in changes.items():
        setattr(item, key, value)
    db.commit(); db.refresh(item)
    return session_out(db, item)

@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str, db: Session = Depends(get_db)):
    item = require(db, StorySession, session_id)
    # A digest is keyed by Thread, so deleting an adopted source Session must
    # invalidate it before the source hash can be reused by a later chat.
    if item.status == "adopted":
        digest = db.get(ThreadContextDigest, item.thread_id)
        if digest is not None:
            db.delete(digest)
    db.delete(item); db.commit()
    return Response(status_code=204)

@router.get("/sessions/{session_id}/messages", response_model=list[MessageWithSourcesOut])
def list_messages(session_id: str, db: Session = Depends(get_db)):
    require(db, StorySession, session_id)
    messages = db.scalars(select(Message).where(Message.session_id == session_id).order_by(Message.created_at, Message.id)).all()
    return [message_out(db, item) for item in messages]

@router.post("/sessions/{session_id}/chat")
async def chat(session_id: str, payload: ChatIn, db: Session = Depends(get_db)):
    current = require(db, StorySession, session_id)
    web_sources: list[FetchResult] = []
    inferred_queries = [payload.content[:500]] if not payload.web_search_queries and WEB_SEARCH_REQUEST.search(payload.content) else []
    search_queries = [*payload.web_search_queries, *inferred_queries]
    inferred_urls = URL_PATTERN.findall(payload.content)
    fetch_urls = list(dict.fromkeys([*payload.fetch_urls, *inferred_urls]))[:5]
    try:
        for query in search_queries:
            web_sources.extend(await search_and_fetch(query))
        for url in fetch_urls:
            web_sources.append(await fetch_one(url))
    except Exception as exc:
        logger.warning("Web retrieval failed for session %s: %s", session_id, exc)
        raise HTTPException(status_code=502, detail=f"Web取得に失敗しました: {exc}") from exc
    if (search_queries or fetch_urls) and not web_sources:
        raise HTTPException(status_code=502, detail="Web検索結果の本文を取得できませんでした。検索語を変えて再試行してください。")
    history = list(db.scalars(select(Message).where(Message.session_id == session_id).order_by(Message.created_at, Message.id)))
    plan = await build_context_plan(db, current, payload.content, history, web_sources)
    user_message = Message(session_id=session_id, role="user", content=payload.content)
    db.add(user_message); db.commit()
    prompt = [{"role": "system", "content": plan.system_text}]
    prompt.extend({"role": item.role.value if hasattr(item.role, "value") else str(item.role), "content": item.content} for item in plan.history)
    prompt.append({"role": "user", "content": payload.content})
    stream_session_factory = sessionmaker(bind=db.get_bind(), autoflush=False, expire_on_commit=False)

    async def events() -> AsyncIterator[str]:
        parts: list[str] = []
        assistant_id: str | None = None
        try:
            async for token in llm.stream_completion(prompt):
                parts.append(token)
                if assistant_id is None:
                    with stream_session_factory() as save_db:
                        assistant = Message(session_id=session_id, role="assistant", content="", model=llm.settings.openai_model, metadata_json={"generation_status": "streaming"})
                        save_db.add(assistant); save_db.commit(); assistant_id = assistant.id
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
            with stream_session_factory() as save_db:
                assistant = save_db.get(Message, assistant_id) if assistant_id else Message(session_id=session_id, role="assistant", content="", model=llm.settings.openai_model)
                assistant.content = "".join(parts); assistant.metadata_json = {"generation_status": "completed"}; save_db.add(assistant); save_db.flush()
                for result in web_sources: persist_source(save_db, session_id, result, message_id=assistant.id)
                save_db.commit(); save_db.refresh(assistant)
                final_message = message_out(save_db, assistant).model_dump(by_alias=True, mode="json")
            yield f"event: done\ndata: {json.dumps({'message': final_message}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except BaseException as exc:
            interrupted_message: dict | None = None
            if assistant_id:
                with stream_session_factory() as save_db:
                    assistant = save_db.get(Message, assistant_id)
                    if assistant:
                        assistant.content = "".join(parts); assistant.metadata_json = {"generation_status": "interrupted"}
                        for result in web_sources:
                            if not save_db.scalar(select(Source.id).where(Source.message_id == assistant.id, Source.url == result.url)):
                                persist_source(save_db, session_id, result, message_id=assistant.id)
                        save_db.commit()
                        save_db.refresh(assistant)
                        interrupted_message = message_out(save_db, assistant).model_dump(by_alias=True, mode="json")
            logger.exception("LLM streaming failed for session %s", session_id)
            if isinstance(exc, Exception):
                yield f"event: error\ndata: {json.dumps({'content': 'LLMへの接続または生成に失敗しました。設定とサーバー状態を確認してください。', 'message': interrupted_message}, ensure_ascii=False)}\n\n"
            else:
                raise

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@router.post("/sessions/{session_id}/web-search", response_model=list[SourceOut])
async def web_search(session_id: str, payload: WebSearchIn, db: Session = Depends(get_db)):
    require(db, StorySession, session_id)
    try:
        results = await search_and_fetch(payload.query)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    sources = [persist_source(db, session_id, result) for result in results]
    db.commit()
    for source in sources:
        db.refresh(source)
    return sources

@router.post("/sessions/{session_id}/web-fetch", response_model=SourceOut, status_code=201)
async def web_fetch(session_id: str, payload: WebFetchIn, db: Session = Depends(get_db)):
    require(db, StorySession, session_id)
    try:
        result = await fetch_one(payload.url)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    source = persist_source(db, session_id, result)
    db.commit(); db.refresh(source)
    return source

@router.post("/sessions/{session_id}/summary", response_model=SummaryOut)
async def generate_summary(session_id: str, db: Session = Depends(get_db)):
    current = require(db, StorySession, session_id)
    messages = list(db.scalars(select(Message).where(Message.session_id == session_id).order_by(Message.created_at, Message.id)))
    if not messages:
        raise HTTPException(status_code=400, detail="This session has no messages")
    transcript = "\n\n".join(f"{(m.role.value if hasattr(m.role, 'value') else m.role).upper()}: {m.content}" for m in messages)
    instruction = (
        "次の会話で、ユーザーが最終的に採用した設定・決定事項だけを簡潔な箇条書きで整理してください。"
        "検討途中、却下、推測、AIが提案しただけの事項は含めないでください。出力は要約案であり自動確定されません。"
    )
    summary = await llm.complete([{"role": "system", "content": instruction}, {"role": "user", "content": f"SESSION: {current.title}\n\n{transcript}"}])
    return SummaryOut(summary=summary)

@router.put("/sessions/{session_id}/summary", response_model=SessionOut)
def save_summary(session_id: str, payload: SummaryIn, db: Session = Depends(get_db)):
    current = require(db, StorySession, session_id)
    current.adoption_summary = payload.summary.strip() or None
    if current.adoption_summary:
        current.status = "adopted"
    elif current.status == "adopted":
        current.status = "considering"
    db.commit(); db.refresh(current)
    return session_out(db, current)

@router.get("/sessions/{session_id}/context", response_model=ContextInspectorOut)
async def context_inspector(session_id: str, db: Session = Depends(get_db)):
    current = require(db, StorySession, session_id)
    history = list(db.scalars(select(Message).where(Message.session_id == current.id).order_by(Message.created_at, Message.id)))
    latest_user = next((item for item in reversed(history) if (item.role.value if hasattr(item.role, "value") else str(item.role)) == "user"), None)
    planning_history = [item for item in history if item is not latest_user]
    plan = await build_context_plan(db, current, latest_user.content if latest_user else "", planning_history)
    return inspector_out(db, current, plan, history)

@router.post("/sessions/{session_id}/context/preview", response_model=ContextInspectorOut)
async def context_preview(session_id: str, payload: ContextPreviewIn, db: Session = Depends(get_db)):
    current = require(db, StorySession, session_id)
    history = list(db.scalars(select(Message).where(Message.session_id == current.id).order_by(Message.created_at, Message.id)))
    plan = await build_context_plan(db, current, payload.content, history)
    return inspector_out(db, current, plan, history)

@router.get("/sessions/{session_id}/sources", response_model=list[SourceOut])
def list_sources(session_id: str, db: Session = Depends(get_db)):
    require(db, StorySession, session_id)
    return db.scalars(select(Source).where(Source.session_id == session_id).order_by(Source.fetched_at.desc())).all()

@router.post("/sessions/{session_id}/sources", response_model=SourceOut, status_code=201)
def create_source(session_id: str, payload: SourceCreate, db: Session = Depends(get_db)):
    require(db, StorySession, session_id)
    item = Source(session_id=session_id, **payload.model_dump()); db.add(item); db.commit(); db.refresh(item)
    return item

@router.get("/search", response_model=list[SearchResult])
def search(
    q: str = Query(min_length=1), project_id: str | None = None, thread_id: str | None = None,
    status: str | None = None, archived: bool | None = None, db: Session = Depends(get_db),
):
    pattern = f"%{q}%"
    results: list[SearchResult] = []
    project_query = select(Project).where(or_(Project.title.ilike(pattern), Project.description.ilike(pattern)))
    if project_id: project_query = project_query.where(Project.id == project_id)
    for item in db.scalars(project_query.limit(50)):
        results.append(SearchResult(id=item.id, type="project", title=item.title, excerpt=item.description, project_id=item.id))

    thread_query = select(Thread).where(or_(Thread.title.ilike(pattern), Thread.description.ilike(pattern)))
    if project_id: thread_query = thread_query.where(Thread.project_id == project_id)
    if thread_id: thread_query = thread_query.where(Thread.id == thread_id)
    for item in db.scalars(thread_query.limit(50)):
        results.append(SearchResult(id=item.id, type="thread", title=item.title, excerpt=item.description, project_id=item.project_id, thread_id=item.id))

    session_query = select(StorySession, Thread.project_id).join(Thread).where(or_(StorySession.title.ilike(pattern), StorySession.adoption_summary.ilike(pattern)))
    if project_id: session_query = session_query.where(Thread.project_id == project_id)
    if thread_id: session_query = session_query.where(StorySession.thread_id == thread_id)
    if status: session_query = session_query.where(StorySession.status == status)
    if archived is not None: session_query = session_query.where(StorySession.archived == archived)
    for item, parent_project_id in db.execute(session_query.limit(100)):
        results.append(SearchResult(id=item.id, type="session", title=item.title, excerpt=item.adoption_summary, project_id=parent_project_id, thread_id=item.thread_id, session_id=item.id, status=item.status, archived=item.archived))

    message_query = select(Message, StorySession, Thread.project_id).join(StorySession, Message.session_id == StorySession.id).join(Thread, StorySession.thread_id == Thread.id).where(Message.content.ilike(pattern))
    if project_id: message_query = message_query.where(Thread.project_id == project_id)
    if thread_id: message_query = message_query.where(StorySession.thread_id == thread_id)
    if status: message_query = message_query.where(StorySession.status == status)
    if archived is not None: message_query = message_query.where(StorySession.archived == archived)
    for message, parent_session, parent_project_id in db.execute(message_query.limit(100)):
        results.append(SearchResult(id=message.id, type="message", title=parent_session.title, excerpt=message.content[:300], project_id=parent_project_id, thread_id=parent_session.thread_id, session_id=parent_session.id, status=parent_session.status, archived=parent_session.archived))
    return results[:200]
