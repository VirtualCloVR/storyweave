from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from .api import router
from .config import settings
from .db import SessionLocal
from .models import Character, CharacterFact, Project, StorySession, Thread, ThreadCharacter, ThreadSceneFact

def seed() -> None:
    if not settings.seed_enabled:
        return
    with SessionLocal() as db:
        if db.scalar(select(Project.id).limit(1)):
            return
        project = Project(title="MyGO ワンライト", description="Development seed")
        thread = Thread(title="愛音事故SS", project=project)
        thread.sessions = [
            StorySession(title="事故要素を入れるとして現実的な事故と表現", status="adopted", adoption_summary="- 愛音は自転車で事故に遭う\n- 意識は失わない"),
            StorySession(title="燈が事故を知る流れ", status="considering"),
            StorySession(title="記憶喪失案", status="rejected"),
        ]
        anon = Character(name="千早愛音", source_title="BanG Dream! It's MyGO!!!!!", aliases=["愛音", "あのんちゃん"])
        anon.facts = [
            CharacterFact(key="身長", value="160cm", sort_order=0),
            CharacterFact(key="誕生日", value="9/8", sort_order=1),
            CharacterFact(key="学年", value="高等部1年A組", sort_order=2),
        ]
        thread.characters = [ThreadCharacter(character=anon, always_include=False, sort_order=0)]
        thread.scene_facts = [
            ThreadSceneFact(key="舞台", value="無人島", sort_order=0),
            ThreadSceneFact(key="半球", value="北半球", sort_order=1),
            ThreadSceneFact(key="季節", value="夏", sort_order=2),
        ]
        db.add(project); db.commit()

@asynccontextmanager
async def lifespan(_: FastAPI):
    seed()
    yield

app = FastAPI(title="Storyweave API", version="0.2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=False, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Content-Type", "Accept"])
app.include_router(router)

@app.get("/health")
def root_health() -> dict[str, str]:
    return {"status": "ok"}
