import secrets

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.database import get_db
from api.db.models import Agent

router = APIRouter(prefix="/agents", tags=["agents"])


class AgentCreate(BaseModel):
    name: str
    owner_id: str


router.post("/register")


async def register_agent(body: AgentCreate, db: AsyncSession = Depends(get_db)):
    api_key = secrets.token_urlsafe(32)
    agent = Agent(
        id=api_key,
        name=body.name,
        owner_id=body.owner_id,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
