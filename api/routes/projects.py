import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic.main import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.sql.expression import text

from api.db.database import get_db
from api.db.models import Project, ProjectStatus, Task, TaskStatus

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    title: str
    goal: str
    owner_id: str
    budget: int = 0
    reviewer_type: str = "human"


@router.post("/")
async def create_project(body: ProjectCreate, db: AsyncSession = Depends(get_db)):
    project = Project(
        id=uuid.uuid4(),
        title=body.title,
        goal=body.goal,
        owner_id=body.owner_id,
        budget=body.budget,
    )
    db.add(project)
    await db.flush()
    task = Task(
        id=uuid.uuid4(),
        project_id=project.id,
        title="First task",
        description=body.goal,
        status=TaskStatus.open,
        credits=10,
    )
    db.add(task)
    await db.commit()
    return {
        "project_id": str(project.id),
        "title": project.title,
        "task_created": 1,
        "status": project.status.value,
    }


@router.get("/")
async def list_projects(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).order_by(Project.created_at.desc()))
    projects = result.scalars().all()
    return [
        {
            "id": str(p.id),
            "title": p.title,
            "status": p.status.value,
            "budget": p.budget,
            "created_at": p.created_at,
        }
        for p in projects
    ]
