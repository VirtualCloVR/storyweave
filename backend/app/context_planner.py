from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from . import llm
from .config import settings
from .context_builder import DEFAULT_SYSTEM_PROMPT, adopted_sessions_for_context
from .models import Character, Message, Project, StorySession, Thread, ThreadCharacter, ThreadContextDigest, ThreadSceneFact
from .tools import FetchResult
from .web import format_source_context

DigestGenerator = Callable[[list[StorySession], int], Awaitable[str]]


@dataclass
class PlannedCharacter:
    id: str
    name: str
    included: bool
    reason: str | None
    facts: list[tuple[str, str, int]] = field(default_factory=list)


@dataclass
class ContextPlan:
    system_text: str
    history: list[Message]
    cast_text: str
    character_text: str
    scene_text: str
    canon_text: str
    web_text: str
    characters: list[PlannedCharacter]
    scene_facts: list[tuple[str, str, int]]
    adopted_sessions: list[StorySession]
    relevant_sessions: list[StorySession]
    sizes: dict[str, int]
    total_chars: int
    budget_chars: int
    compression_mode: str
    digest_status: str
    compression_degraded: bool


def normalize_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\r", "\\r").replace("\n", "\\n").replace("|", "\\|").replace("=", "\\=")


def compact_facts(facts: list[tuple[str, str, int]]) -> str:
    return " | ".join(f"{_escape(key)}={_escape(value)}" for key, value, _ in sorted(facts, key=lambda item: item[2]))


def serialize_character(name: str, facts: list[tuple[str, str, int]]) -> str:
    return f"[CHARACTER {_escape(name)}]\n{compact_facts(facts)}" if facts else f"[CHARACTER {_escape(name)}]"


def serialize_scene(facts: list[tuple[str, str, int]]) -> str:
    return f"[SCENE]\n{compact_facts(facts)}" if facts else ""


def canon_source_hash(items: list[StorySession]) -> str:
    payload = [
        {
            "id": item.id,
            "updated_at": item.updated_at.isoformat() if item.updated_at else "",
            "status": item.status.value if hasattr(item.status, "value") else str(item.status),
            "title": item.title,
            "adoption_summary": item.adoption_summary or "",
        }
        for item in items
    ]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def digest_freshness(digest: ThreadContextDigest | None, source_hash: str) -> str:
    if digest is None:
        return "unused"
    return "fresh" if digest.source_hash == source_hash else "stale"


def _canon_block(item: StorySession) -> str:
    return f"[{item.title}]\n{item.adoption_summary.strip()}"


def _full_canon(items: list[StorySession]) -> str:
    return "\n\n".join(_canon_block(item) for item in items)


def _mention_text(current_user_message: str, history: list[Message], max_chars: int = 4_000) -> str:
    chunks = [current_user_message]
    used = len(current_user_message)
    for item in reversed(history):
        role = item.role.value if hasattr(item.role, "value") else str(item.role)
        if role != "user":
            continue
        remaining = max_chars - used
        if remaining <= 0:
            break
        chunks.append(item.content[-remaining:])
        used += min(len(item.content), remaining)
    return normalize_text("\n".join(chunks))


def _mentioned(character: Character, normalized_haystack: str) -> bool:
    candidates = [character.name, *(character.aliases or [])]
    return any((needle := normalize_text(value).strip()) and needle in normalized_haystack for value in candidates)


def _ngrams(value: str) -> set[str]:
    normalized = re.sub(r"\s+", "", normalize_text(value))
    grams: set[str] = set()
    for size in (2, 3):
        grams.update(normalized[index:index + size] for index in range(max(0, len(normalized) - size + 1)))
    return grams


def relevant_adopted_sessions(items: list[StorySession], query: str, limit: int = 3) -> list[StorySession]:
    query_normalized = normalize_text(query)
    query_grams = _ngrams(query)
    scored: list[tuple[int, int, StorySession]] = []
    for index, item in enumerate(items):
        candidate = f"{item.title}\n{item.adoption_summary or ''}"
        candidate_normalized = normalize_text(candidate)
        overlap = len(query_grams & _ngrams(candidate))
        substring_bonus = 20 if query_normalized.strip() and query_normalized.strip() in candidate_normalized else 0
        score = overlap + substring_bonus
        if score:
            scored.append((score, -index, item))
    scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return [row[2] for row in scored[:limit]]


def _pack_history(items: list[Message], max_chars: int) -> list[Message]:
    selected: list[Message] = []
    used = 0
    for item in reversed(items):
        if selected and used + len(item.content) > max_chars:
            break
        if len(item.content) > max_chars and not selected:
            continue
        selected.append(item)
        used += len(item.content)
    return list(reversed(selected))


def _collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _fallback_digest(items: list[StorySession], relevant: list[StorySession], target_chars: int) -> tuple[str, bool]:
    ordered = [*relevant, *(item for item in items if item not in relevant)]
    blocks: list[str] = []
    used = 0
    for item in ordered:
        block = f"[{_collapse_whitespace(item.title)}] {_collapse_whitespace(item.adoption_summary or '')}"
        extra = len(block) + (1 if blocks else 0)
        if used + extra > target_chars:
            continue
        blocks.append(block)
        used += extra
    return "\n".join(blocks), len(blocks) < len(items)


DIGEST_INSTRUCTION = (
    "以下の採用済み確定設定だけを圧縮してください。新しい事実を追加せず、不明点を補完せず、矛盾を勝手に解消しないでください。"
    "名前・数値・時間・場所・関係性を可能な限り保持し、短さより事実保持を優先してください。"
)


async def generate_canon_digest(items: list[StorySession], target_chars: int) -> str:
    max_chunk_chars = max(12_000, target_chars * 3)
    chunks: list[list[StorySession]] = []
    current: list[StorySession] = []
    current_chars = 0
    for item in items:
        block_size = len(_canon_block(item))
        if block_size > max_chunk_chars:
            raise ValueError("A single adopted Session exceeds the safe digest input size")
        if current and current_chars + block_size > max_chunk_chars:
            chunks.append(current)
            current, current_chars = [], 0
        current.append(item)
        current_chars += block_size
    if current:
        chunks.append(current)

    digests: list[str] = []
    for chunk in chunks:
        digests.append(await llm.complete([
            {"role": "system", "content": DIGEST_INSTRUCTION},
            {"role": "user", "content": f"目標は約{target_chars}文字以内です。\n\n{_full_canon(chunk)}"},
        ]))
    if len(digests) == 1:
        return digests[0].strip()
    return (await llm.complete([
        {"role": "system", "content": DIGEST_INSTRUCTION},
        {"role": "user", "content": f"次のChunk Digestを最終的に約{target_chars}文字以内へ統合してください。\n\n" + "\n\n".join(digests)},
    ])).strip()


def _render_system(instruction: str, project: Project, thread: Thread, current: StorySession, cast_text: str, character_text: str, scene_text: str, canon_text: str, web_text: str, degraded: bool) -> str:
    warning = "\n\nCONTEXT WARNING\n一部の確定設定がContext Budgetにより省略されている可能性があります。未提示の設定を勝手に断定しないでください。" if degraded else ""
    sections = [
        f"SYSTEM\n{instruction}",
        f"PROJECT\n{project.title}",
        f"THREAD\n{thread.title}",
        f"CAST\n{cast_text or '（登録なし）'}",
        f"CHARACTER CONTEXT\n{character_text or '（今回投入されるCharacter Factはありません）'}",
        f"SCENE CONTEXT\n{scene_text or '（Scene Factはありません）'}",
        f"CONFIRMED CANON\n{canon_text or '（採用済みの確定事項はまだありません）'}",
        f"CURRENT SESSION\n{current.title}",
    ]
    if web_text:
        sections.append(web_text)
    return "\n\n".join(sections) + warning


async def build_context_plan(
    db: Session,
    current: StorySession,
    current_user_message: str,
    recent_history: list[Message],
    web_sources: list[FetchResult] | None = None,
    *,
    digest_generator: DigestGenerator = generate_canon_digest,
) -> ContextPlan:
    thread = db.get(Thread, current.thread_id)
    if thread is None:
        raise ValueError("Session is not attached to a thread")
    project = db.get(Project, thread.project_id)
    if project is None:
        raise ValueError("Thread is not attached to a project")

    links = list(db.execute(
        select(ThreadCharacter)
        .where(ThreadCharacter.thread_id == thread.id)
        .options(joinedload(ThreadCharacter.character).joinedload(Character.facts))
        .order_by(ThreadCharacter.sort_order, ThreadCharacter.character_id)
    ).unique().scalars())
    mention_text = _mention_text(current_user_message, recent_history)
    characters: list[PlannedCharacter] = []
    included_blocks: list[str] = []
    for link in links:
        reason = "always_include" if link.always_include else ("mentioned" if _mentioned(link.character, mention_text) else None)
        facts = [(fact.key, fact.value, fact.sort_order) for fact in link.character.facts]
        planned = PlannedCharacter(link.character.id, link.character.name, reason is not None, reason, facts)
        characters.append(planned)
        if planned.included:
            included_blocks.append(serialize_character(planned.name, facts))

    scene_rows = list(db.scalars(
        select(ThreadSceneFact).where(ThreadSceneFact.thread_id == thread.id).order_by(ThreadSceneFact.sort_order, ThreadSceneFact.id)
    ))
    scene_facts = [(fact.key, fact.value, fact.sort_order) for fact in scene_rows]
    cast_text = " / ".join(link.character.name for link in links)
    character_text = "\n\n".join(included_blocks)
    scene_text = serialize_scene(scene_facts)
    adopted = adopted_sessions_for_context(db, current)
    full_canon = _full_canon(adopted)
    selected_history = _pack_history(recent_history, settings.context_history_max_chars)
    web_text = format_source_context(web_sources or [], max_chars=settings.context_web_max_chars)
    instruction = project.system_prompt.strip() if project.system_prompt else DEFAULT_SYSTEM_PROMPT

    empty_system = _render_system(instruction, project, thread, current, cast_text, character_text, scene_text, "", "", False)
    full_priority_total = len(empty_system) + len(full_canon) + len(web_text) + len(current_user_message)
    compression_mode = "full"
    digest_status = "unused"
    compression_degraded = False
    relevant: list[StorySession] = []
    canon_text = full_canon

    if adopted and full_priority_total > settings.context_budget_chars:
        compression_mode = "digest"
        relevance_query = current_user_message + "\n" + "\n".join(
            item.content for item in selected_history if (item.role.value if hasattr(item.role, "value") else str(item.role)) == "user"
        )
        relevant = relevant_adopted_sessions(adopted, relevance_query)
        source_hash = canon_source_hash(adopted)
        digest = db.get(ThreadContextDigest, thread.id)
        digest_status = digest_freshness(digest, source_hash)
        digest_content = digest.content if digest_status == "fresh" else ""
        if not digest_content:
            try:
                digest_content = (await digest_generator(adopted, settings.context_digest_target_chars)).strip()
                if not digest_content:
                    raise ValueError("Digest generator returned empty content")
                if digest is None:
                    digest = ThreadContextDigest(thread_id=thread.id, content=digest_content, source_hash=source_hash, source_session_count=len(adopted), source_chars=len(full_canon), model=llm.settings.openai_model or None)
                    db.add(digest)
                else:
                    digest.content = digest_content
                    digest.source_hash = source_hash
                    digest.source_session_count = len(adopted)
                    digest.source_chars = len(full_canon)
                    digest.model = llm.settings.openai_model or None
                db.commit()
                digest_status = "generated"
            except Exception:
                digest_content, dropped = _fallback_digest(adopted, relevant, settings.context_digest_target_chars)
                compression_degraded = dropped
                digest_status = "failed"
        if len(digest_content) > settings.context_digest_target_chars:
            digest_content = digest_content[:settings.context_digest_target_chars]
            compression_degraded = True
        canon_parts = [f"[CANON DIGEST]\n{digest_content}"]
        for item in relevant:
            block = f"[RELEVANT SESSION: {item.title}]\n{item.adoption_summary.strip()}"
            if block not in canon_parts:
                canon_parts.append(block)
        canon_text = "\n\n".join(canon_parts)

    system_text = _render_system(instruction, project, thread, current, cast_text, character_text, scene_text, canon_text, web_text, compression_degraded)
    total = len(system_text) + sum(len(item.content) for item in selected_history) + len(current_user_message)
    while selected_history and total > settings.context_budget_chars:
        removed = selected_history.pop(0)
        total -= len(removed.content)
    if total > settings.context_budget_chars and web_text:
        excess = total - settings.context_budget_chars
        web_text = format_source_context(web_sources or [], max_chars=max(0, len(web_text) - excess))
        system_text = _render_system(instruction, project, thread, current, cast_text, character_text, scene_text, canon_text, web_text, compression_degraded)
        total = len(system_text) + sum(len(item.content) for item in selected_history) + len(current_user_message)
    if total > settings.context_budget_chars and compression_mode == "digest" and canon_text:
        excess = total - settings.context_budget_chars
        canon_text = canon_text[:max(0, len(canon_text) - excess)]
        compression_degraded = True
        system_text = _render_system(instruction, project, thread, current, cast_text, character_text, scene_text, canon_text, web_text, True)
        total = len(system_text) + sum(len(item.content) for item in selected_history) + len(current_user_message)
        if total > settings.context_budget_chars and canon_text:
            canon_text = canon_text[:max(0, len(canon_text) - (total - settings.context_budget_chars))]
            system_text = _render_system(instruction, project, thread, current, cast_text, character_text, scene_text, canon_text, web_text, True)
            total = len(system_text) + sum(len(item.content) for item in selected_history) + len(current_user_message)

    sizes = {
        "system": len(system_text) - len(character_text) - len(scene_text) - len(canon_text) - len(web_text),
        "characters": len(character_text),
        "scene": len(scene_text),
        "canon": len(canon_text),
        "history": sum(len(item.content) for item in selected_history),
        "web": len(web_text),
        "currentUserMessage": len(current_user_message),
    }
    return ContextPlan(system_text, selected_history, cast_text, character_text, scene_text, canon_text, web_text, characters, scene_facts, adopted, relevant, sizes, total, settings.context_budget_chars, compression_mode, digest_status, compression_degraded)
