import uuid
from fastapi import APIRouter, Depends
from fastapi.exceptions import HTTPException
from fastapi.routing import DecoratedCallable
from sqlalchemy import select
from sqlalchemy.ext.asyncio.session import AsyncSession

from api.db.database import get_db
from api.db.models import Project, Task, TaskStatus

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/open")
async def list_tasks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Task).where(Task.status==TaskStatus.open).order_by(Task.created_at.desc()))
    tasks = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "title": t.title,
            "status": t.status.value,
            "skills_required":t.skills_required,
            "description": t.description,
            "project_id": t.project_id,
            "credits": t.credits,
            "created_at": t.created_at,
        }
        for t in tasks
    ]
@router.post(f"/{task_id}/claim")
async def claim_task
@router.get(f"/{task_id}/context")
async def get_context(task_id:str,db:AsyncSession=Depends(get_db)):
    task=await db.get(Task,uuid.UUID(task_id))
    if not task:
        raise HTTPException(404,"Task not found")
    #for basic mem right now TODO :mke beterrrr
    project=await db.get(Project,task.project_id)
    if not project:
        raise HTTPException(404,"project not found")
    #for now get the tasks that are compeleted and pass thought json
    result=await db.execute(
        select(Task).where(Task.project_id==task.project_id,task.status==TaskStatus.approved)
    )
    completed=result.scalars().all()
    return {
        "task":{
            "id":str(task.id),
            "title":task.title,
            "description":task.description,
            "done_when":task.done_when,
            "skills_required":task.skills_required,
            "credits":task.credits
        },
        "project":{
            "id":str(project.id),
            "goal":project.goal
        },
        "memory":[
            {
            "title":t.title,
            "description":t.description
            }
        for t in completed
        ]
    }
