import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.database import get_db
from api.db.models import Agent

router = APIRouter(prefix="/agents", tags=["agents"])


class AgentCreate(BaseModel):
    name: str
    owner_id: str


@router.post("/register")
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
    return {
        "id": api_key,
        "name": agent.name,
        "owner_id": agent.owner_id,
        "created_at": agent.created_at,
    }


@router.get("/{agent_id}")
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    data = await db.get(Agent, agent_id)
    if not data:
        raise HTTPException(404, "agent not found")
    return {
        "id": data.id,
        "name": data.name,
        "owner_id": data.owner_id,
        "created_at": data.created_at,
        "total_credits": data.total_credits,
        "tasks_done": data.tasks_done,
    }
