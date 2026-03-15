from fastapi import FastAPI

from api.db.database import engine
from api.db.models import Base
from api.routes import projects, task

app = FastAPI(title="Dispatch API")
app.include_router(projects.router)
app.include_router(task.router)


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.get("/")
async def root():
    return {"status": "dispatcher is rnning"}
