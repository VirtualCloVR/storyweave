from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from .api import router
from .config import settings
from .db import Base, SessionLocal, engine
from .models import Project, StorySession, Thread

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
        db.add(project); db.commit()

@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    seed()
    yield

app = FastAPI(title="Storyweave API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=False, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Content-Type", "Accept"])
app.include_router(router)

@app.get("/health")
def root_health() -> dict[str, str]:
    return {"status": "ok"}

