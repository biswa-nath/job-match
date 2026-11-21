"""Add is_active flag (and jobs.deactivated_on) for closed postings

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-21
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

active_flag = postgresql.ENUM("yes", "no", name="active_flag", create_type=False)


def upgrade() -> None:
    active_flag.create(op.get_bind(), checkfirst=True)
    for table in ("jobs", "job_matches"):
        op.add_column(
            table,
            sa.Column("is_active", active_flag, nullable=False, server_default="yes"),
        )
    op.add_column(
        "jobs", sa.Column("deactivated_on", sa.TIMESTAMP(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("jobs", "deactivated_on")
    for table in ("job_matches", "jobs"):
        op.drop_column(table, "is_active")
    active_flag.drop(op.get_bind(), checkfirst=True)
