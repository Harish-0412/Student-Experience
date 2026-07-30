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


def uuid4() -> uuid.UUID:
    return uuid.uuid4()


class Competency(TimestampMixin, Base):
    __tablename__ = "competencies"
    __table_args__ = (
        CheckConstraint("version > 0", name="version_positive"),
        Index("ix_competencies_category_active", "category", "active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    prerequisite_slugs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class StudentCompetency(TimestampMixin, Base):
    __tablename__ = "student_competencies"
    __table_args__ = (
        UniqueConstraint(
            "student_id", "competency_id", name="uq_student_competencies_student_competency"
        ),
        CheckConstraint(
            "proficiency_level >= 0 AND proficiency_level <= 5",
            name="proficiency_valid",
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_valid"),
        Index("ix_student_competencies_student", "student_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    competency_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("competencies.id", ondelete="CASCADE"), nullable=False
    )
    proficiency_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="self_reported")
    evidence_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    last_evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class GoalTemplate(TimestampMixin, Base):
    __tablename__ = "goal_templates"
    __table_args__ = (
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint("default_duration_weeks > 0", name="duration_positive"),
        CheckConstraint(
            "default_target_level >= 1 AND default_target_level <= 5",
            name="target_level_valid",
        ),
        Index("ix_goal_templates_category_active", "category", "active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    matching_terms: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    default_duration_weeks: Mapped[int] = mapped_column(Integer, nullable=False)
    default_target_level: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    measurable_outcome: Mapped[str] = mapped_column(String(500), nullable=False)
    success_criteria: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    requirements: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class GoalIntelligenceState(TimestampMixin, Base):
    __tablename__ = "goal_intelligence_states"
    __table_args__ = (CheckConstraint("version > 0", name="version_positive"),)

    goal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("goals.id", ondelete="CASCADE"), primary_key=True
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("goal_templates.id", ondelete="SET NULL")
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    clarification: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    feasibility: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    skill_gap: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    graph_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class GoalGraphNode(TimestampMixin, Base):
    __tablename__ = "goal_graph_nodes"
    __table_args__ = (
        CheckConstraint("sequence_order >= 0", name="sequence_nonnegative"),
        CheckConstraint("estimated_hours >= 0", name="hours_nonnegative"),
        Index("ix_goal_graph_nodes_goal_sequence", "goal_id", "sequence_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    goal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("goals.id", ondelete="CASCADE"), nullable=False
    )
    competency_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("competencies.id", ondelete="SET NULL")
    )
    node_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    required_level: Mapped[int | None] = mapped_column(Integer)
    current_level: Mapped[int | None] = mapped_column(Integer)
    estimated_hours: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_optional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    node_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )


class GoalGraphEdge(Base):
    __tablename__ = "goal_graph_edges"
    __table_args__ = (
        UniqueConstraint(
            "goal_id",
            "source_node_id",
            "target_node_id",
            "relationship_type",
            name="uq_goal_graph_edges_relationship",
        ),
        CheckConstraint("source_node_id <> target_node_id", name="not_self_referential"),
        Index("ix_goal_graph_edges_goal", "goal_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    goal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("goals.id", ondelete="CASCADE"), nullable=False
    )
    source_node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("goal_graph_nodes.id", ondelete="CASCADE"), nullable=False
    )
    target_node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("goal_graph_nodes.id", ondelete="CASCADE"), nullable=False
    )
    relationship_type: Mapped[str] = mapped_column(
        String(40), nullable=False, default="prerequisite"
    )
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class DecisionCard(TimestampMixin, Base):
    __tablename__ = "decision_cards"
    __table_args__ = (
        CheckConstraint(
            "status IN ('proposed', 'accepted', 'rejected', 'superseded')",
            name="status_allowed",
        ),
        Index("ix_decision_cards_goal_type", "goal_id", "decision_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    goal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("goals.id", ondelete="CASCADE"), nullable=False
    )
    decision_type: Mapped[str] = mapped_column(String(60), nullable=False)
    decision: Mapped[str] = mapped_column(String(500), nullable=False)
    reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    evidence: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    alternatives: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    approval_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="proposed")
    agent_name: Mapped[str] = mapped_column(String(120), nullable=False)
