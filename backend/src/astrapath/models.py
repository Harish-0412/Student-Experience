import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from astrapath.db import Base, TimestampMixin, utc_now
from astrapath.enums import AgentRunStatus, GoalStatus, Role, UserStatus, WorkflowStatus


def uuid4() -> uuid.UUID:
    return uuid.uuid4()


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("oidc_issuer", "oidc_subject", name="uq_users_oidc_identity"),
        CheckConstraint("role IN ('student', 'admin')", name="role_allowed"),
        CheckConstraint(
            "status IN ('active', 'suspended', 'deleted')", name="status_allowed"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    role: Mapped[Role] = mapped_column(
        Enum(Role, native_enum=False, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
        default=Role.STUDENT,
    )
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, native_enum=False, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
        default=UserStatus.ACTIVE,
    )
    password_hash: Mapped[str | None] = mapped_column(String(512))
    oidc_issuer: Mapped[str | None] = mapped_column(String(512))
    oidc_subject: Mapped[str | None] = mapped_column(String(255))
    auth_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    profile: Mapped["StudentProfile | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    goals: Mapped[list["Goal"]] = relationship(back_populates="student")


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("auth_sessions.id", ondelete="SET NULL")
    )
    user_agent: Mapped[str | None] = mapped_column(String(512))
    ip_address: Mapped[str | None] = mapped_column(String(64))


class StudentProfile(TimestampMixin, Base):
    __tablename__ = "student_profiles"
    __table_args__ = (
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint(
            "weekly_learning_minutes >= 0 AND weekly_learning_minutes <= 10080",
            name="weekly_minutes_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Kolkata")
    locale: Mapped[str] = mapped_column(String(16), nullable=False, default="en-IN")
    education_level: Mapped[str | None] = mapped_column(String(120))
    institution: Mapped[str | None] = mapped_column(String(200))
    weekly_learning_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    learning_preferences: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    availability: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    device_access: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    accessibility_needs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    consent_scopes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user: Mapped[User] = relationship(back_populates="profile")
    versions: Mapped[list["StudentProfileVersion"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )


class StudentProfileVersion(Base):
    __tablename__ = "student_profile_versions"
    __table_args__ = (
        UniqueConstraint("profile_id", "version", name="uq_profile_versions_profile_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    changed_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    change_reason: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    profile: Mapped[StudentProfile] = relationship(back_populates="versions")


class Goal(TimestampMixin, Base):
    __tablename__ = "goals"
    __table_args__ = (
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint("priority >= 1 AND priority <= 5", name="priority_valid"),
        CheckConstraint(
            "status IN ('draft', 'active', 'paused', 'completed', 'closed')",
            name="status_allowed",
        ),
        Index("ix_goals_student_status", "student_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    raw_statement: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(80))
    target_date: Mapped[date | None] = mapped_column(Date)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    status: Mapped[GoalStatus] = mapped_column(
        Enum(
            GoalStatus,
            native_enum=False,
            values_callable=lambda e: [x.value for x in e],
        ),
        nullable=False,
        default=GoalStatus.DRAFT,
    )
    success_criteria: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    assumptions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    student: Mapped[User] = relationship(back_populates="goals")
    versions: Mapped[list["GoalVersion"]] = relationship(
        back_populates="goal", cascade="all, delete-orphan"
    )


class GoalVersion(Base):
    __tablename__ = "goal_versions"
    __table_args__ = (
        UniqueConstraint("goal_id", "version", name="uq_goal_versions_goal_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    goal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("goals.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    changed_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    change_type: Mapped[str] = mapped_column(String(40), nullable=False)
    change_reason: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    goal: Mapped[Goal] = relationship(back_populates="versions")


class WorkflowState(TimestampMixin, Base):
    __tablename__ = "workflow_states"
    __table_args__ = (
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint(
            "status IN ('pending', 'running', 'input_required', 'approval_required', "
            "'completed', 'failed', 'cancelled')",
            name="status_allowed",
        ),
        Index("ix_workflow_states_student_status", "student_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    workflow_type: Mapped[str] = mapped_column(String(80), nullable=False)
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    goal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("goals.id", ondelete="CASCADE")
    )
    status: Mapped[WorkflowStatus] = mapped_column(
        Enum(
            WorkflowStatus,
            native_enum=False,
            values_callable=lambda e: [x.value for x in e],
        ),
        nullable=False,
        default=WorkflowStatus.PENDING,
    )
    current_step: Mapped[str] = mapped_column(String(80), nullable=False, default="created")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    state_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentRun(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_agent_runs_idempotency_key"),
        CheckConstraint(
            "status IN ('running', 'completed', 'input_required', "
            "'student_approval_required', 'admin_review_required', 'blocked', 'failed')",
            name="status_allowed",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_states.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_name: Mapped[str] = mapped_column(String(120), nullable=False)
    agent_version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[AgentRunStatus] = mapped_column(
        Enum(
            AgentRunStatus,
            native_enum=False,
            values_callable=lambda e: [x.value for x in e],
        ),
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    model_route: Mapped[str] = mapped_column(String(80), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    output_hash: Mapped[str | None] = mapped_column(String(64))
    output_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
        Index("ix_audit_logs_student_time", "student_id", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    actor_role: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(64), nullable=False)
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    request_id: Mapped[str | None] = mapped_column(String(64))
    correlation_id: Mapped[str | None] = mapped_column(String(64))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    before_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    after_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    event_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    previous_hash: Mapped[str | None] = mapped_column(String(64))
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)


class AuditChainHead(Base):
    __tablename__ = "audit_chain_heads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    current_hash: Mapped[str | None] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


@event.listens_for(AuditLog, "before_update")
def prevent_audit_update(_mapper: Any, _connection: Any, _target: AuditLog) -> None:
    raise ValueError("Audit records are immutable")


@event.listens_for(AuditLog, "before_delete")
def prevent_audit_delete(_mapper: Any, _connection: Any, _target: AuditLog) -> None:
    raise ValueError("Audit records are immutable")
