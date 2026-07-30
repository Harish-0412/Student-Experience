"""phase 2 goal intelligence

Revision ID: 8a1f4d2c7b90
Revises: 3ec66d7f2e87
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8a1f4d2c7b90"
down_revision: str | None = "3ec66d7f2e87"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "competencies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("prerequisite_slugs", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version > 0", name=op.f("ck_competencies_version_positive")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_competencies")),
    )
    op.create_index(
        "ix_competencies_category_active",
        "competencies",
        ["category", "active"],
        unique=False,
    )
    op.create_index(op.f("ix_competencies_slug"), "competencies", ["slug"], unique=True)

    op.create_table(
        "goal_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("matching_terms", sa.JSON(), nullable=False),
        sa.Column("default_duration_weeks", sa.Integer(), nullable=False),
        sa.Column("default_target_level", sa.Integer(), nullable=False),
        sa.Column("measurable_outcome", sa.String(length=500), nullable=False),
        sa.Column("success_criteria", sa.JSON(), nullable=False),
        sa.Column("requirements", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "default_duration_weeks > 0",
            name=op.f("ck_goal_templates_duration_positive"),
        ),
        sa.CheckConstraint(
            "default_target_level >= 1 AND default_target_level <= 5",
            name=op.f("ck_goal_templates_target_level_valid"),
        ),
        sa.CheckConstraint(
            "version > 0", name=op.f("ck_goal_templates_version_positive")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_goal_templates")),
    )
    op.create_index(
        "ix_goal_templates_category_active",
        "goal_templates",
        ["category", "active"],
        unique=False,
    )
    op.create_index(
        op.f("ix_goal_templates_slug"), "goal_templates", ["slug"], unique=True
    )

    op.create_table(
        "student_competencies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("competency_id", sa.Uuid(), nullable=False),
        sa.Column("proficiency_level", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("last_evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name=op.f("ck_student_competencies_confidence_valid"),
        ),
        sa.CheckConstraint(
            "proficiency_level >= 0 AND proficiency_level <= 5",
            name=op.f("ck_student_competencies_proficiency_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["competency_id"],
            ["competencies.id"],
            name=op.f("fk_student_competencies_competency_id_competencies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["users.id"],
            name=op.f("fk_student_competencies_student_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_student_competencies")),
        sa.UniqueConstraint(
            "student_id",
            "competency_id",
            name="uq_student_competencies_student_competency",
        ),
    )
    op.create_index(
        "ix_student_competencies_student",
        "student_competencies",
        ["student_id"],
        unique=False,
    )

    op.create_table(
        "goal_intelligence_states",
        sa.Column("goal_id", sa.Uuid(), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("clarification", sa.JSON(), nullable=True),
        sa.Column("feasibility", sa.JSON(), nullable=True),
        sa.Column("skill_gap", sa.JSON(), nullable=True),
        sa.Column("graph_summary", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "version > 0", name=op.f("ck_goal_intelligence_states_version_positive")
        ),
        sa.ForeignKeyConstraint(
            ["goal_id"],
            ["goals.id"],
            name=op.f("fk_goal_intelligence_states_goal_id_goals"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["goal_templates.id"],
            name=op.f("fk_goal_intelligence_states_template_id_goal_templates"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("goal_id", name=op.f("pk_goal_intelligence_states")),
    )

    op.create_table(
        "goal_graph_nodes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("goal_id", sa.Uuid(), nullable=False),
        sa.Column("competency_id", sa.Uuid(), nullable=True),
        sa.Column("node_type", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("required_level", sa.Integer(), nullable=True),
        sa.Column("current_level", sa.Integer(), nullable=True),
        sa.Column("estimated_hours", sa.Float(), nullable=False),
        sa.Column("sequence_order", sa.Integer(), nullable=False),
        sa.Column("is_optional", sa.Boolean(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "estimated_hours >= 0",
            name=op.f("ck_goal_graph_nodes_hours_nonnegative"),
        ),
        sa.CheckConstraint(
            "sequence_order >= 0",
            name=op.f("ck_goal_graph_nodes_sequence_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["competency_id"],
            ["competencies.id"],
            name=op.f("fk_goal_graph_nodes_competency_id_competencies"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["goal_id"],
            ["goals.id"],
            name=op.f("fk_goal_graph_nodes_goal_id_goals"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_goal_graph_nodes")),
    )
    op.create_index(
        "ix_goal_graph_nodes_goal_sequence",
        "goal_graph_nodes",
        ["goal_id", "sequence_order"],
        unique=False,
    )

    op.create_table(
        "goal_graph_edges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("goal_id", sa.Uuid(), nullable=False),
        sa.Column("source_node_id", sa.Uuid(), nullable=False),
        sa.Column("target_node_id", sa.Uuid(), nullable=False),
        sa.Column("relationship_type", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source_node_id <> target_node_id",
            name=op.f("ck_goal_graph_edges_not_self_referential"),
        ),
        sa.ForeignKeyConstraint(
            ["goal_id"],
            ["goals.id"],
            name=op.f("fk_goal_graph_edges_goal_id_goals"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_node_id"],
            ["goal_graph_nodes.id"],
            name=op.f("fk_goal_graph_edges_source_node_id_goal_graph_nodes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_node_id"],
            ["goal_graph_nodes.id"],
            name=op.f("fk_goal_graph_edges_target_node_id_goal_graph_nodes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_goal_graph_edges")),
        sa.UniqueConstraint(
            "goal_id",
            "source_node_id",
            "target_node_id",
            "relationship_type",
            name="uq_goal_graph_edges_relationship",
        ),
    )
    op.create_index(
        "ix_goal_graph_edges_goal",
        "goal_graph_edges",
        ["goal_id"],
        unique=False,
    )

    op.create_table(
        "decision_cards",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("goal_id", sa.Uuid(), nullable=False),
        sa.Column("decision_type", sa.String(length=60), nullable=False),
        sa.Column("decision", sa.String(length=500), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("alternatives", sa.JSON(), nullable=False),
        sa.Column("approval_required", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("agent_name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('proposed', 'accepted', 'rejected', 'superseded')",
            name=op.f("ck_decision_cards_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["goal_id"],
            ["goals.id"],
            name=op.f("fk_decision_cards_goal_id_goals"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_decision_cards")),
    )
    op.create_index(
        "ix_decision_cards_goal_type",
        "decision_cards",
        ["goal_id", "decision_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_decision_cards_goal_type", table_name="decision_cards")
    op.drop_table("decision_cards")
    op.drop_index("ix_goal_graph_edges_goal", table_name="goal_graph_edges")
    op.drop_table("goal_graph_edges")
    op.drop_index("ix_goal_graph_nodes_goal_sequence", table_name="goal_graph_nodes")
    op.drop_table("goal_graph_nodes")
    op.drop_table("goal_intelligence_states")
    op.drop_index("ix_student_competencies_student", table_name="student_competencies")
    op.drop_table("student_competencies")
    op.drop_index(op.f("ix_goal_templates_slug"), table_name="goal_templates")
    op.drop_index("ix_goal_templates_category_active", table_name="goal_templates")
    op.drop_table("goal_templates")
    op.drop_index(op.f("ix_competencies_slug"), table_name="competencies")
    op.drop_index("ix_competencies_category_active", table_name="competencies")
    op.drop_table("competencies")
