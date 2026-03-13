import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends
from fastapi.exceptions import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio.session import AsyncSession

from api.db.database import get_db
from api.db.models import Project, Task, TaskStatus

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/open")
async def list_tasks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Task)
        .where(Task.status == TaskStatus.open)
        .order_by(Task.created_at.desc())
    )
    tasks = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "title": t.title,
            "status": t.status.value,
            "skills_required": t.skills_required,
            "description": t.description,
            "project_id": t.project_id,
            "credits": t.credits,
            "created_at": t.created_at,
        }
        for t in tasks
    ]


@router.post("/{task_id}/claim")
async def claim_task(task_id: str, agent_id: str, db: AsyncSession = Depends(get_db)):
    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(400, "Invalid task ID format")
    task = await db.get(Task, task_uuid)
    if not task:
        raise HTTPException(404, "Task not found")
    if task.status != TaskStatus.open:
        raise HTTPException(409, "Task already claimed")
    task.status = TaskStatus.claimed
    task.claimed_by = agent_id
    task.claimed_at = datetime.now(UTC)
    await db.commit()
    return {
        "status": "claimed",
        "task_id": str(task.id),
        "claimed_by": agent_id,
        "claimed_at": task.claimed_at,
    }


@router.get("/{task_id}/context")
async def get_context(task_id: str, db: AsyncSession = Depends(get_db)):
    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(400, "Invalid task ID format — must be a UUID")
    task = await db.get(Task, task_uuid)
    if not task:
        raise HTTPException(404, "Task not found")
    # for basic mem right now TODO :mke beterrrr
    project = await db.get(Project, task.project_id)
    if not project:
        raise HTTPException(404, "project not found")
    # for now get the tasks that are compeleted and pass thought json
    result = await db.execute(
        select(Task).where(
            Task.project_id == task.project_id, Task.status == TaskStatus.approved
        )
    )
    completed = result.scalars().all()
    return {
        "task": {
            "id": str(task.id),
            "title": task.title,
            "description": task.description,
            "done_when": task.done_when,
            "skills_required": task.skills_required,
            "credits": task.credits,
        },
        "project": {"id": str(project.id), "goal": project.goal},
        "memory": [{"title": t.title, "description": t.description} for t in completed],
    }
