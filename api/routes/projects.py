import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic.main import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio.session import AsyncSession

from api.db.database import get_db
from api.db.models import Project, ProjectMessages, Task, TaskStatus
from api.services.decomposer import decompose_project

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    title: str
    goal: str
    owner_id: str
    budget: int = 0
    reviewer_type: str = "human"


class MessageCreate(BaseModel):
    agent_id: str
    content: str
    parent_id: str | None = None


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

    # decompose into tasks
    tasks_data = decompose_project(body.goal)

    for t in tasks_data:
        task = Task(
            id=uuid.uuid4(),
            project_id=project.id,
            title=t["title"],
            description=t["description"],
            done_when=t.get("done_when"),
            skills_required=t.get("skills_required", []),
            credits=t.get("credits", 10),
            order_index=t.get("order_index", 0),
            status=TaskStatus.open,
        )
        db.add(task)

    await db.commit()
    await db.refresh(project)

    return {
        "project_id": str(project.id),
        "title": project.title,
        "status": project.status.value,
        "tasks_created": len(tasks_data),
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


@router.get("/{project_id}")
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    try:
        project_uuid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(400, "Invalid project ID")
    project = await db.get(Project, project_uuid)
    if not project:
        raise HTTPException(404, "project not found")
    result = await db.execute(
        select(Task)
        .where(Task.project_id == project_uuid)
        .order_by(Task.order_index.desc())
    )
    tasks = result.scalars().all()
    return {
        "id": str(project.id),
        "title": project.title,
        "goal": project.goal,
        "status": project.status.value,
        "category": project.category,
        "budget": project.budget,
        "reviewer_type": project.reviewer_type.value,
        "repo_path": project.repo_path,
        "created_at": project.created_at,
        "tasks": [
            {
                "id": str(t.id),
                "title": t.title,
                "status": t.status.value,
                "credits": t.credits,
                "order_index": t.order_index,
                "claimed_by": t.claimed_by,
            }
            for t in tasks
        ],
    }


@router.post("/{project_id}/messages")
async def post_messages(
    body: MessageCreate, project_id: str, db: AsyncSession = Depends(get_db)
):
    try:
        project_uuid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(400, "invalid project id")
    project = await db.get(Project, project_uuid)
    if not project:
        raise HTTPException(404, "project not found")
    message = ProjectMessages(
        id=uuid.uuid4(),
        project_id=project_uuid,
        agent_id=body.agent_id,
        content=body.content,
        parent_id=uuid.UUID(str(body.parent_id)) if body.parent_id else None,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return {
        "id": str(message.id),
        "agent_id": message.agent_id,
        "content": message.content,
        "created_at": message.created_at,
    }


@router.get("/{project_id}/messages")
async def get_messages(
    project_id: str, limit: int = 50, db: AsyncSession = Depends(get_db)
):
    try:
        project_uuid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(400, "invalid project id")
    project = await db.get(Project, project_uuid)
    if not project:
        raise HTTPException(404, "Project not found")
    result = await db.execute(
        select(ProjectMessages)
        .where(ProjectMessages.project_id == project_uuid)
        .order_by(ProjectMessages.created_at.desc())
        .limit(limit)
    )
    messages = result.scalars().all()
    return [
        {
            "id": str(m.id),
            "agent_id": m.agent_id,
            "content": m.content,
            "created_at": m.created_at,
            "parent_id": str(m.parent_id) if m.parent_id else None,
        }
        for m in messages
    ]
