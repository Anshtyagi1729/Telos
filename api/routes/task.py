import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from fastapi.exceptions import HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio.session import AsyncSession

from api.db.database import get_db
from api.db.models import (
    Project,
    ProjectMessages,
    Submission,
    SubmissionStatus,
    Task,
    TaskStatus,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskSubmit(BaseModel):
    agent_id: str
    output: str
    commit_hash: str | None
    parent_hash: str | None


class TaskReview(BaseModel):
    approved: bool
    reviewer_id: str
    review_notes: str | None


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
            "project_id": str(t.project_id),
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
    task.expires_at = datetime.now(UTC) + timedelta(minutes=50)
    await db.commit()
    await db.refresh(task)
    return {
        "status": "claimed",
        "task_id": str(task.id),
        "claimed_by": agent_id,
        "claimed_at": task.claimed_at,
    }


@router.post("/{task_id}/submit")
async def submit_task(
    task_id: str, body: TaskSubmit, db: AsyncSession = Depends(get_db)
):

    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(400, "Invalid task ID")

    task = await db.get(Task, task_uuid)
    if not task:
        raise HTTPException(404, "Task not found")
    if task.claimed_by != body.agent_id:
        raise HTTPException(403, "This task is not claimed by you")
    if task.status != TaskStatus.claimed:
        raise HTTPException(409, "Task is not in claimed status")

    # get current highest version for this task
    result = await db.execute(
        select(Submission)
        .where(Submission.task_id == task_uuid)
        .order_by(Submission.version.desc())
        .limit(1)
    )
    latest = result.scalars().first()
    next_version = (latest.version + 1) if latest else 1

    submission = Submission(
        id=uuid.uuid4(),
        task_id=task_uuid,
        agent_id=body.agent_id,
        output=body.output,
        version=next_version,
        commit_hash=body.commit_hash,
        parent_hash=body.parent_hash,
    )
    db.add(submission)
    await db.flush()
    # update task status + point to active submission
    task.status = TaskStatus.submitted
    task.active_submission_id = submission.id

    await db.commit()

    return {
        "status": "submitted",
        "submission_id": str(submission.id),
        "version": next_version,
    }


@router.post("/{task_id}/review")
async def review_task(
    task_id: str, body: TaskReview, db: AsyncSession = Depends(get_db)
):
    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(400, "Invalid task ID")

    task = await db.get(Task, task_uuid)
    if not task:
        raise HTTPException(404, "Task not found")
    if task.status != TaskStatus.submitted:
        raise HTTPException(409, "Task is not submitted yet")
    if not task.active_submission_id:
        raise HTTPException(400, "No active submission found")

    submission = await db.get(Submission, task.active_submission_id)

    if body.approved:
        # approve submission
        submission.status = SubmissionStatus.approved
        submission.reviewed_by = body.reviewer_id
        submission.review_notes = body.review_notes
        submission.credits_paid = task.credits
        task.status = TaskStatus.approved

        # auto post approval to message board
        db.add(
            ProjectMessages(
                id=uuid.uuid4(),
                project_id=task.project_id,
                agent_id="system",
                content=f"Task '{task.title}' approved by {body.reviewer_id}. Commit: {submission.commit_hash or 'N/A'}",
            )
        )

    else:
        # reject — task goes back to open for another agent
        submission.status = SubmissionStatus.rejected
        submission.reviewed_by = body.reviewer_id
        submission.review_notes = body.review_notes
        task.status = TaskStatus.open
        task.claimed_by = None
        task.claimed_at = None
        task.expires_at = None
        task.active_submission_id = None

        # auto post rejection to message board
        db.add(
            ProjectMessages(
                id=uuid.uuid4(),
                project_id=task.project_id,
                agent_id="system",
                content=f"Task '{task.title}' rejected: {body.review_notes or 'No reason given'}",
            )
        )

    await db.commit()

    return {
        "status": "approved" if body.approved else "rejected",
        "task_id": str(task.id),
        "credits_paid": submission.credits_paid if body.approved else 0,
    }


# TODO this will change to include the contet from the message board and git repo of the base project
@router.get("/{task_id}/context")
async def get_context(
    task_id: str, limit: int = 30, db: AsyncSession = Depends(get_db)
):
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
        select(ProjectMessages)
        .where(ProjectMessages.project_id == project.id)
        .order_by(ProjectMessages.created_at.desc())
        .limit(limit)
    )
    messages = result.scalars().all()
    return {
        "task": {
            "id": str(task.id),
            "title": task.title,
            "description": task.description,
            "done_when": task.done_when,
            "skills_required": task.skills_required,
            "credits": task.credits,
        },
        "project": {
            "id": str(project.id),
            "goal": project.goal,
            "clone_url": f"http://localhost:8000/repos/{project.id}.git",
            "latest_commit": project.latest_commit,
        },
        "messages": [
            {"agent_id": m.agent_id, "content": m.content, "created_at": m.created_at}
            for m in reversed(messages)
        ],
    }
