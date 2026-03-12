import enum
import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql.elements import True_
from sqlalchemy.sql.expression import false, true

Base = declarative_base()


class ProjectStatus(enum.Enum):
    active = "active"
    completed = "completed"
    in_review = "in_review"
    cancelled = "cancelled"


class TaskStatus(enum.Enum):
    open = "open"
    claimed = "claimed"
    blocked = "blocked"
    submitted = "submitted"
    approved = "approved"
    rejected = "rejected"


class SubmissionStatus(enum.Enum):
    pending = "pending"
    approved = "approved"
    in_review = "in_review"
    rejected = "rejected"


class ReviewerType(enum.Enum):
    human = "human"
    agent = "agent"


class Project(Base):
    __tablename__ = "projects"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    goal = Column(Text, nullable=False)
    status = Column(Enum(ProjectStatus), default=ProjectStatus.active)
    owner_id = Column(String, nullable=False)
    reviewer_type = Column(Enum(ReviewerType), default=ReviewerType.human)
    budget = Column(Integer, default=0)
    category = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True), default=datetime.now(UTC), onupdate=datetime.now(UTC)
    )
    tasks = relationship("Task", back_populates="project", cascade="all,delete-orphan")


class Task(Base):
    __tablename__ = "tasks"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    done_when = Column(Text, nullable=True)
    skills_required = Column(ARRAY(String), default=[])
    status = Column(Enum(TaskStatus), default=TaskStatus.open)
    order_index = Column(Integer, default=0)
    credits = Column(Integer, default=0)
    active_submission_id = Column(
        UUID(as_uuid=True), ForeignKey("submissions.id"), nullable=True
    )
    claimed_by = Column(String, nullable=True)
    claimed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.now(UTC))
    project = relationship("Project", back_populates="tasks")
    submissions = relationship(
        "Submission",
        back_populates="task",
        foreign_keys="Submission.task_id",
        cascade="all, delete-orphan",
    )

    active_submission = relationship(
        "Submission", foreign_keys="Task.active_submission_id", post_update=True
    )


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False)
    agent_id = Column(String, nullable=False)
    output = Column(Text, nullable=False)
    version = Column(Integer, default=1)
    status = Column(Enum(SubmissionStatus), default=SubmissionStatus.pending)
    review_notes = Column(Text, nullable=True)
    reviewed_by = Column(String, nullable=True)
    credits_paid = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.now(UTC))

    task = relationship("Task", foreign_keys=[task_id], back_populates="submissions")


class Agent(Base):
    __tablename__ = "agents"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    owner_id = Column(String, nullable=False)
    total_credits = Column(Integer, default=0)
    tasks_done = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=true), default=datetime.now(UTC))
