from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from .api import router
from .config import settings
from .db import SessionLocal
from .models import Project, StorySession, Thread


def seed() -> None:
    """Create a minimal offline sample when explicitly enabled.

    Only runs when SEED_ENABLED is true and the database is empty.
    Sample: Project "MyGO ワンライト" / Thread "愛音事故SS" /
    Session "交通事故描写の検討" (considering).
    """
    if not settings.seed_enabled:
        return
    with SessionLocal() as db:
        if db.scalar(select(Project.id).limit(1)):
            return
        project = Project(title="MyGO ワンライト", description="Sample workspace")
        thread = Thread(title="愛音事故SS", project=project)
        thread.sessions = [
            StorySession(title="交通事故描写の検討", status="considering"),
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
