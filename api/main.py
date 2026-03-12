from fastapi import FastAPI

from api.db.database import engine
from api.db.models import Base

app = FastAPI(title="Dispatch API")


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.get("/")
async def root():
    return {"status": "dispatcher is rnning"}
