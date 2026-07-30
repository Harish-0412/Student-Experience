import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
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
from astrapath.phase4.enums import (
    AgentExecutionStatus,
    AssessmentStatus,
    AttemptStatus,
    EvidenceStatus,
    FocusSessionStatus,
    ReplanStatus,
    ResourceStatus,
    RiskSeverity,
    RiskStatus,
    TutorMode,
)


def uuid4() -> uuid.UUID:
    return uuid.uuid4()


class ExecutionContext(TimestampMixin, Base):
    __tablename__ = "phase4_execution_contexts"
    __table_args__ = (
        UniqueConstraint("goal_id", name="uq_phase4_execution_contexts_goal"),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint(
            "completed_task_count <= planned_task_count", name="task_totals_valid"
        ),
        CheckConstraint(
            "completed_milestone_count <= planned_milestone_count",
            name="milestone_totals_valid",
        ),
        CheckConstraint(
            "schedule_adherence >= 0 AND schedule_adherence <= 1",
            name="adherence_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    goal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("goals.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan_ref: Mapped[str | None] = mapped_column(String(120))
    plan_version: Mapped[int | None] = mapped_column(Integer)
    planned_task_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_task_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    planned_milestone_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    completed_milestone_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    planned_weekly_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    weekly_capacity_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    schedule_adherence: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0
    )
    source_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class LearningResource(TimestampMixin, Base):
    __tablename__ = "learning_resources"
    __table_args__ = (
        CheckConstraint("difficulty >= 1 AND difficulty <= 5", name="difficulty_valid"),
        CheckConstraint("cost_amount >= 0", name="cost_nonnegative"),
        CheckConstraint(
            "quality_score >= 0 AND quality_score <= 1", name="quality_valid"
        ),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint(
            "status IN ('draft', 'approved', 'rejected', 'stale')",
            name="status_allowed",
        ),
        Index(
            "ix_learning_resources_competency_status",
            "competency_ref",
            "status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    competency_ref: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False, unique=True)
    provider: Mapped[str] = mapped_column(String(160), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(40), nullable=False)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    cost_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    license_name: Mapped[str | None] = mapped_column(String(120))
    content_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    status: Mapped[ResourceStatus] = mapped_column(
        String(20), nullable=False, default=ResourceStatus.DRAFT
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class ResourceRecommendation(Base):
    __tablename__ = "resource_recommendations"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "goal_id",
            "resource_id",
            "request_key",
            name="uq_resource_recommendations_request_resource",
        ),
        CheckConstraint(
            "relevance_score >= 0 AND relevance_score <= 1",
            name="relevance_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    goal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("goals.id", ondelete="CASCADE"), nullable=False
    )
    resource_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learning_resources.id", ondelete="CASCADE"), nullable=False
    )
    competency_ref: Mapped[str] = mapped_column(String(120), nullable=False)
    request_key: Mapped[str] = mapped_column(String(128), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False)
    selection_reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class FocusSession(TimestampMixin, Base):
    __tablename__ = "focus_sessions"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_focus_sessions_idempotency"),
        CheckConstraint("planned_minutes >= 5", name="planned_minutes_valid"),
        CheckConstraint(
            "status IN ('active', 'completed', 'abandoned')", name="status_allowed"
        ),
        CheckConstraint("version > 0", name="version_positive"),
        Index("ix_focus_sessions_student_goal", "student_id", "goal_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    goal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("goals.id", ondelete="CASCADE"), nullable=False
    )
    task_ref: Mapped[str | None] = mapped_column(String(120))
    milestone_ref: Mapped[str | None] = mapped_column(String(120))
    objective: Mapped[str] = mapped_column(String(500), nullable=False)
    planned_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_minutes: Mapped[int | None] = mapped_column(Integer)
    distraction_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    blocker_notes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    reflection: Mapped[str | None] = mapped_column(Text)
    accomplished: Mapped[bool | None] = mapped_column(Boolean)
    status: Mapped[FocusSessionStatus] = mapped_column(
        String(20), nullable=False, default=FocusSessionStatus.ACTIVE
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TutorThread(TimestampMixin, Base):
    __tablename__ = "tutor_threads"
    __table_args__ = (Index("ix_tutor_threads_student_goal", "student_id", "goal_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    goal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("goals.id", ondelete="CASCADE"), nullable=False
    )
    competency_ref: Mapped[str] = mapped_column(String(120), nullable=False)
    mode: Mapped[TutorMode] = mapped_column(
        String(20), nullable=False, default=TutorMode.EXPLAIN
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")


class TutorMessage(Base):
    __tablename__ = "tutor_messages"
    __table_args__ = (Index("ix_tutor_messages_thread_time", "thread_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    thread_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tutor_threads.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    integrity_boundary_applied: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class AssessmentDefinition(TimestampMixin, Base):
    __tablename__ = "assessment_definitions"
    __table_args__ = (
        CheckConstraint(
            "passing_percentage >= 0 AND passing_percentage <= 100",
            name="passing_valid",
        ),
        CheckConstraint("max_score > 0", name="max_score_positive"),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint(
            "status IN ('draft', 'published', 'retired')", name="status_allowed"
        ),
        Index(
            "ix_assessment_definitions_goal_status",
            "goal_id",
            "status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    goal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("goals.id", ondelete="CASCADE"), nullable=False
    )
    competency_ref: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    assessment_type: Mapped[str] = mapped_column(String(40), nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    questions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    rubric: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    max_score: Mapped[float] = mapped_column(Float, nullable=False)
    passing_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    time_limit_minutes: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[AssessmentStatus] = mapped_column(
        String(20), nullable=False, default=AssessmentStatus.DRAFT
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class AssessmentAttempt(Base):
    __tablename__ = "assessment_attempts"
    __table_args__ = (
        UniqueConstraint(
            "assessment_id",
            "student_id",
            "attempt_number",
            name="uq_assessment_attempts_number",
        ),
        UniqueConstraint(
            "idempotency_key", name="uq_assessment_attempts_idempotency"
        ),
        CheckConstraint("percentage >= 0 AND percentage <= 100", name="percentage_valid"),
        CheckConstraint(
            "status IN ('scored', 'review_required')", name="status_allowed"
        ),
        Index("ix_assessment_attempts_student", "student_id", "submitted_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_definitions.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    answers: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    max_score: Mapped[float] = mapped_column(Float, nullable=False)
    percentage: Mapped[float] = mapped_column(Float, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    feedback: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    status: Mapped[AttemptStatus] = mapped_column(String(30), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class StorageReceipt(Base):
    __tablename__ = "phase4_storage_receipts"
    __table_args__ = (
        UniqueConstraint("storage_key", name="uq_phase4_storage_receipts_key"),
        CheckConstraint("size_bytes > 0", name="size_positive"),
        CheckConstraint(
            "scanner_status IN ('clean', 'quarantined')", name="scanner_status_allowed"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    media_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    scanner_status: Mapped[str] = mapped_column(String(20), nullable=False)
    verified_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class EvidenceSubmission(Base):
    __tablename__ = "evidence_submissions"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_evidence_submissions_idempotency"),
        UniqueConstraint(
            "student_id",
            "goal_id",
            "sha256",
            name="uq_evidence_submissions_content",
        ),
        CheckConstraint("size_bytes > 0", name="size_positive"),
        CheckConstraint(
            "status IN ('pending', 'verified', 'rejected', "
            "'resubmission_required', 'admin_review_required')",
            name="status_allowed",
        ),
        Index("ix_evidence_submissions_student_goal", "student_id", "goal_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    goal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("goals.id", ondelete="CASCADE"), nullable=False
    )
    competency_ref: Mapped[str] = mapped_column(String(120), nullable=False)
    task_ref: Mapped[str | None] = mapped_column(String(120))
    milestone_ref: Mapped[str | None] = mapped_column(String(120))
    assessment_attempt_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("assessment_attempts.id", ondelete="SET NULL")
    )
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    content_text: Mapped[str | None] = mapped_column(Text)
    acceptance_criteria: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    status: Mapped[EvidenceStatus] = mapped_column(
        String(40), nullable=False, default=EvidenceStatus.PENDING
    )
    quality_score: Mapped[float | None] = mapped_column(Float)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EvidenceReview(Base):
    __tablename__ = "evidence_reviews"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence_submissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer_type: Mapped[str] = mapped_column(String(20), nullable=False)
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    decision: Mapped[EvidenceStatus] = mapped_column(String(40), nullable=False)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False)
    criteria_results: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    integrity_flags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    feedback: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class ProgressEvent(Base):
    __tablename__ = "progress_events"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_progress_events_idempotency"),
        Index("ix_progress_events_student_goal_time", "student_id", "goal_id", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    goal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("goals.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    activity_points: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    mastery_signal: Mapped[float | None] = mapped_column(Float)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class ProgressSnapshot(Base):
    __tablename__ = "progress_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "goal_id", "version", name="uq_progress_snapshots_goal_version"
        ),
        CheckConstraint("version > 0", name="version_positive"),
        Index("ix_progress_snapshots_goal_time", "goal_id", "as_of"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    goal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("goals.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    activity_progress: Mapped[float] = mapped_column(Float, nullable=False)
    milestone_progress: Mapped[float] = mapped_column(Float, nullable=False)
    mastery_progress: Mapped[float] = mapped_column(Float, nullable=False)
    goal_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    schedule_variance: Mapped[float] = mapped_column(Float, nullable=False)
    verified_evidence_count: Mapped[int] = mapped_column(Integer, nullable=False)
    assessment_count: Mapped[int] = mapped_column(Integer, nullable=False)
    focus_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    calculation: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    as_of: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class MasteryEstimate(Base):
    __tablename__ = "mastery_estimates"
    __table_args__ = (
        UniqueConstraint(
            "goal_id",
            "competency_ref",
            "version",
            name="uq_mastery_estimates_goal_competency_version",
        ),
        CheckConstraint("score >= 0 AND score <= 1", name="score_valid"),
        CheckConstraint(
            "confidence_lower >= 0 AND confidence_lower <= 1",
            name="lower_valid",
        ),
        CheckConstraint(
            "confidence_upper >= 0 AND confidence_upper <= 1",
            name="upper_valid",
        ),
        Index("ix_mastery_estimates_goal_competency", "goal_id", "competency_ref"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    goal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("goals.id", ondelete="CASCADE"), nullable=False
    )
    competency_ref: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_lower: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_upper: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False)
    weak_subskills: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    next_assessment_recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    calculation: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    estimated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class CoachingRecord(Base):
    __tablename__ = "coaching_records"
    __table_args__ = (Index("ix_coaching_records_student_goal", "student_id", "goal_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    goal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("goals.id", ondelete="CASCADE"), nullable=False
    )
    check_in: Mapped[str] = mapped_column(Text, nullable=False)
    motivation_level: Mapped[int] = mapped_column(Integer, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    reflection_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    habit_experiment: Mapped[str] = mapped_column(Text, nullable=False)
    notification_adjustment: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class Risk(Base):
    __tablename__ = "risks"
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 1", name="score_valid"),
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="severity_allowed",
        ),
        CheckConstraint(
            "status IN ('open', 'mitigated', 'dismissed')", name="status_allowed"
        ),
        CheckConstraint("version > 0", name="version_positive"),
        Index("ix_risks_student_goal_status", "student_id", "goal_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    goal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("goals.id", ondelete="CASCADE"), nullable=False
    )
    risk_type: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[RiskSeverity] = mapped_column(String(20), nullable=False)
    status: Mapped[RiskStatus] = mapped_column(
        String(20), nullable=False, default=RiskStatus.OPEN
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    likely_causes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    intervention: Mapped[str] = mapped_column(Text, nullable=False)
    requires_admin_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReplanProposal(TimestampMixin, Base):
    __tablename__ = "replan_proposals"
    __table_args__ = (
        CheckConstraint(
            "status IN ('proposed', 'approved_pending_phase3', 'rejected', 'applied')",
            name="status_allowed",
        ),
        CheckConstraint("version > 0", name="version_positive"),
        Index("ix_replan_proposals_student_goal", "student_id", "goal_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    goal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("goals.id", ondelete="CASCADE"), nullable=False
    )
    risk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("risks.id", ondelete="CASCADE"), nullable=False
    )
    base_plan_ref: Mapped[str] = mapped_column(String(120), nullable=False)
    base_plan_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ReplanStatus] = mapped_column(
        String(40), nullable=False, default=ReplanStatus.PROPOSED
    )
    proposed_patch: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    impact_analysis: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    alternatives: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    preserves_completed_work: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    student_approval_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    admin_review_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    decision_reason: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    applied_plan_ref: Mapped[str | None] = mapped_column(String(120))
    applied_plan_version: Mapped[int | None] = mapped_column(Integer)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_student_unread", "student_id", "read_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    notification_type: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    related_type: Mapped[str | None] = mapped_column(String(80))
    related_id: Mapped[str | None] = mapped_column(String(128))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class Phase4AgentRun(Base):
    __tablename__ = "phase4_agent_runs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_phase4_agent_runs_idempotency"),
        CheckConstraint(
            "status IN ('running', 'completed', 'input_required', 'admin_review_required', "
            "'student_approval_required', 'blocked', 'failed')",
            name="status_allowed",
        ),
        Index("ix_phase4_agent_runs_student_goal", "student_id", "goal_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    goal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("goals.id", ondelete="SET NULL")
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    agent_name: Mapped[str] = mapped_column(String(120), nullable=False)
    agent_version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[AgentExecutionStatus] = mapped_column(String(40), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
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
