"""serialize audit chain writes

Revision ID: f3a912e7d4b0
Revises: be21515c6e1c
Create Date: 2026-07-30 15:20:00.000000
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "f3a912e7d4b0"
down_revision: str | None = "be21515c6e1c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_chain_heads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("current_hash", sa.String(length=64), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_chain_heads")),
    )
    connection = op.get_bind()
    latest_hash = connection.execute(
        sa.text(
            "SELECT event_hash FROM audit_logs "
            "ORDER BY occurred_at DESC, id DESC LIMIT 1"
        )
    ).scalar_one_or_none()
    record_count = connection.execute(
        sa.text("SELECT COUNT(*) FROM audit_logs")
    ).scalar_one()
    connection.execute(
        sa.text(
            "INSERT INTO audit_chain_heads "
            "(id, current_hash, version, updated_at) "
            "VALUES (:id, :current_hash, :version, :updated_at)"
        ),
        {
            "id": 1,
            "current_hash": latest_hash,
            "version": record_count,
            "updated_at": datetime.now(UTC),
        },
    )


def downgrade() -> None:
    op.drop_table("audit_chain_heads")
