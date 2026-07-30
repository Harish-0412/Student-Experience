"""phase 3 planning engine

Revision ID: c4d9e3f1a672
Revises: 8a1f4d2c7b90
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4d9e3f1a672"
down_revision: str | None = "8a1f4d2c7b90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learning_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("goal_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("total_estimated_minutes", sa.Integer(), nullable=False),
        sa.Column("generation_constraints", sa.JSON(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('proposed', 'approved', 'rejected', 'superseded')",
            name=op.f("ck_learning_plans_status_allowed"),
        ),
        sa.CheckConstraint(
            "version > 0", name=op.f("ck_learning_plans_version_positive")
        ),
        sa.ForeignKeyConstraint(
            ["goal_id"],
            ["goals.id"],
            name=op.f("fk_learning_plans_goal_id_goals"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["users.id"],
            name=op.f("fk_learning_plans_student_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_learning_plans")),
        sa.UniqueConstraint(
            "goal_id", "version", name="uq_learning_plans_goal_version"
        ),
    )
    op.create_index(
        "ix_learning_plans_student_status",
        "learning_plans",
        ["student_id", "status"],
        unique=False,
    )

    op.create_table(
        "milestones",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("goal_id", sa.Uuid(), nullable=False),
        sa.Column("graph_node_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("acceptance_criteria", sa.JSON(), nullable=False),
        sa.Column("evidence_requirements", sa.JSON(), nullable=False),
        sa.Column("dependency_ids", sa.JSON(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False),
        sa.Column("buffer_minutes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "buffer_minutes >= 0",
            name=op.f("ck_milestones_buffer_minutes_nonnegative"),
        ),
        sa.CheckConstraint(
            "estimated_minutes > 0",
            name=op.f("ck_milestones_estimated_minutes_positive"),
        ),
        sa.CheckConstraint(
            "sequence_number > 0",
            name=op.f("ck_milestones_sequence_positive"),
        ),
        sa.CheckConstraint(
            "status IN ('planned', 'in_progress', 'completed', 'blocked', 'dropped')",
            name=op.f("ck_milestones_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["goal_id"],
            ["goals.id"],
            name=op.f("fk_milestones_goal_id_goals"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["graph_node_id"],
            ["goal_graph_nodes.id"],
            name=op.f("fk_milestones_graph_node_id_goal_graph_nodes"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["learning_plans.id"],
            name=op.f("fk_milestones_plan_id_learning_plans"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_milestones")),
        sa.UniqueConstraint(
            "plan_id", "sequence_number", name="uq_milestones_plan_sequence"
        ),
    )
    op.create_index(
        "ix_milestones_goal_target",
        "milestones",
        ["goal_id", "target_date"],
        unique=False,
    )

    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("goal_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("milestone_id", sa.Uuid(), nullable=False),
        sa.Column("competency_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("task_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False),
        sa.Column("scheduled_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence_required", sa.Boolean(), nullable=False),
        sa.Column("evidence_description", sa.String(length=500), nullable=True),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "estimated_minutes > 0",
            name=op.f("ck_tasks_estimated_minutes_positive"),
        ),
        sa.CheckConstraint(
            "priority >= 1 AND priority <= 5",
            name=op.f("ck_tasks_priority_valid"),
        ),
        sa.CheckConstraint(
            "sequence_number > 0", name=op.f("ck_tasks_sequence_positive")
        ),
        sa.CheckConstraint(
            "status IN ('planned', 'ready', 'in_progress', 'completed', "
            "'blocked', 'dropped')",
            name=op.f("ck_tasks_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["competency_id"],
            ["competencies.id"],
            name=op.f("fk_tasks_competency_id_competencies"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["goal_id"],
            ["goals.id"],
            name=op.f("fk_tasks_goal_id_goals"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["milestone_id"],
            ["milestones.id"],
            name=op.f("fk_tasks_milestone_id_milestones"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["learning_plans.id"],
            name=op.f("fk_tasks_plan_id_learning_plans"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["users.id"],
            name=op.f("fk_tasks_student_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tasks")),
        sa.UniqueConstraint(
            "plan_id", "sequence_number", name="uq_tasks_plan_sequence"
        ),
    )
    op.create_index(
        "ix_tasks_goal_status", "tasks", ["goal_id", "status"], unique=False
    )
    op.create_index(
        "ix_tasks_student_schedule",
        "tasks",
        ["student_id", "scheduled_start"],
        unique=False,
    )

    op.create_table(
        "schedules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("weekly_capacity_minutes", sa.Integer(), nullable=False),
        sa.Column("allocated_minutes", sa.Integer(), nullable=False),
        sa.Column("buffer_minutes", sa.Integer(), nullable=False),
        sa.Column("schedule_health_score", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("conflicts", sa.JSON(), nullable=False),
        sa.Column("alternatives", sa.JSON(), nullable=False),
        sa.Column("constraints", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "allocated_minutes >= 0",
            name=op.f("ck_schedules_allocated_nonnegative"),
        ),
        sa.CheckConstraint(
            "buffer_minutes >= 0",
            name=op.f("ck_schedules_buffer_nonnegative"),
        ),
        sa.CheckConstraint(
            "schedule_health_score >= 0 AND schedule_health_score <= 1",
            name=op.f("ck_schedules_health_score_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('proposed', 'approved', 'rejected', 'superseded')",
            name=op.f("ck_schedules_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["learning_plans.id"],
            name=op.f("fk_schedules_plan_id_learning_plans"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["users.id"],
            name=op.f("fk_schedules_student_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_schedules")),
        sa.UniqueConstraint("plan_id", name=op.f("uq_schedules_plan_id")),
    )
    op.create_index(
        "ix_schedules_student_range",
        "schedules",
        ["student_id", "starts_on", "ends_on"],
        unique=False,
    )

    op.create_table(
        "plan_decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("changes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "decision IN ('approved', 'rejected', 'edited')",
            name=op.f("ck_plan_decisions_decision_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_plan_decisions_actor_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["learning_plans.id"],
            name=op.f("fk_plan_decisions_plan_id_learning_plans"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plan_decisions")),
    )
    op.create_index(
        "ix_plan_decisions_plan_time",
        "plan_decisions",
        ["plan_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "schedule_blocks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("schedule_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("block_type", sa.String(length=30), nullable=False),
        sa.Column("energy_level", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "ends_at > starts_at",
            name=op.f("ck_schedule_blocks_positive_duration"),
        ),
        sa.CheckConstraint(
            "status IN ('planned', 'completed', 'cancelled', 'missed')",
            name=op.f("ck_schedule_blocks_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["learning_plans.id"],
            name=op.f("fk_schedule_blocks_plan_id_learning_plans"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["schedule_id"],
            ["schedules.id"],
            name=op.f("fk_schedule_blocks_schedule_id_schedules"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["users.id"],
            name=op.f("fk_schedule_blocks_student_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            name=op.f("fk_schedule_blocks_task_id_tasks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_schedule_blocks")),
    )
    op.create_index(
        "ix_schedule_blocks_student_time",
        "schedule_blocks",
        ["student_id", "starts_at", "ends_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_schedule_blocks_student_time", table_name="schedule_blocks"
    )
    op.drop_table("schedule_blocks")
    op.drop_index("ix_plan_decisions_plan_time", table_name="plan_decisions")
    op.drop_table("plan_decisions")
    op.drop_index("ix_schedules_student_range", table_name="schedules")
    op.drop_table("schedules")
    op.drop_index("ix_tasks_student_schedule", table_name="tasks")
    op.drop_index("ix_tasks_goal_status", table_name="tasks")
    op.drop_table("tasks")
    op.drop_index("ix_milestones_goal_target", table_name="milestones")
    op.drop_table("milestones")
    op.drop_index(
        "ix_learning_plans_student_status", table_name="learning_plans"
    )
    op.drop_table("learning_plans")
