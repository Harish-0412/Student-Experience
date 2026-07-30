import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from astrapath.db import Base, TimestampMixin, utc_now


def uuid4() -> uuid.UUID:
    return uuid.uuid4()


class LearningPlan(TimestampMixin, Base):
    __tablename__ = "learning_plans"
    __table_args__ = (
        UniqueConstraint("goal_id", "version", name="uq_learning_plans_goal_version"),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint(
            "status IN ('proposed', 'approved', 'rejected', 'superseded')",
            name="status_allowed",
        ),
        Index("ix_learning_plans_student_status", "student_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    goal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("goals.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="proposed")
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    generation_constraints: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Milestone(TimestampMixin, Base):
    __tablename__ = "milestones"
    __table_args__ = (
        UniqueConstraint("plan_id", "sequence_number", name="uq_milestones_plan_sequence"),
        CheckConstraint("sequence_number > 0", name="sequence_positive"),
        CheckConstraint("estimated_minutes > 0", name="estimated_minutes_positive"),
        CheckConstraint("buffer_minutes >= 0", name="buffer_minutes_nonnegative"),
        CheckConstraint(
            "status IN ('planned', 'in_progress', 'completed', 'blocked', 'dropped')",
            name="status_allowed",
        ),
        Index("ix_milestones_goal_target", "goal_id", "target_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learning_plans.id", ondelete="CASCADE"), nullable=False
    )
    goal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("goals.id", ondelete="CASCADE"), nullable=False
    )
    graph_node_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("goal_graph_nodes.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned")
    acceptance_criteria: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    evidence_requirements: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    dependency_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    buffer_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Task(TimestampMixin, Base):
    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("plan_id", "sequence_number", name="uq_tasks_plan_sequence"),
        CheckConstraint("sequence_number > 0", name="sequence_positive"),
        CheckConstraint("priority >= 1 AND priority <= 5", name="priority_valid"),
        CheckConstraint("estimated_minutes > 0", name="estimated_minutes_positive"),
        CheckConstraint(
            "status IN ('planned', 'ready', 'in_progress', 'completed', 'blocked', 'dropped')",
            name="status_allowed",
        ),
        Index("ix_tasks_student_schedule", "student_id", "scheduled_start"),
        Index("ix_tasks_goal_status", "goal_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learning_plans.id", ondelete="CASCADE"), nullable=False
    )
    goal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("goals.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    milestone_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("milestones.id", ondelete="CASCADE"), nullable=False
    )
    competency_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("competencies.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    task_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned")
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduled_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scheduled_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    evidence_description: Mapped[str | None] = mapped_column(String(500))
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    task_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )


class Schedule(TimestampMixin, Base):
    __tablename__ = "schedules"
    __table_args__ = (
        CheckConstraint(
            "status IN ('proposed', 'approved', 'rejected', 'superseded')",
            name="status_allowed",
        ),
        CheckConstraint(
            "schedule_health_score >= 0 AND schedule_health_score <= 1",
            name="health_score_valid",
        ),
        CheckConstraint("allocated_minutes >= 0", name="allocated_nonnegative"),
        CheckConstraint("buffer_minutes >= 0", name="buffer_nonnegative"),
        Index("ix_schedules_student_range", "student_id", "starts_on", "ends_on"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learning_plans.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    weekly_capacity_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    allocated_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    buffer_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    schedule_health_score: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="proposed")
    conflicts: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    alternatives: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    constraints: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class ScheduleBlock(TimestampMixin, Base):
    __tablename__ = "schedule_blocks"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="positive_duration"),
        CheckConstraint(
            "status IN ('planned', 'completed', 'cancelled', 'missed')",
            name="status_allowed",
        ),
        Index("ix_schedule_blocks_student_time", "student_id", "starts_at", "ends_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    schedule_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learning_plans.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    block_type: Mapped[str] = mapped_column(String(30), nullable=False, default="study")
    energy_level: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned")


class PlanDecision(Base):
    __tablename__ = "plan_decisions"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('approved', 'rejected', 'edited')",
            name="decision_allowed",
        ),
        Index("ix_plan_decisions_plan_time", "plan_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learning_plans.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    changes: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
