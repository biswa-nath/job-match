"""Add is_active flag (and jobs.deactivated_on) for closed postings

Idempotent (IF NOT EXISTS), like 0001, so a database where the columns were
added by hand or where alembic_version was lost is adopted as-is.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-21
"""

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
        op.execute(
            f"ALTER TABLE {table} "
            "ADD COLUMN IF NOT EXISTS is_active active_flag NOT NULL DEFAULT 'yes'"
        )
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS deactivated_on TIMESTAMPTZ")


def downgrade() -> None:
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS deactivated_on")
    for table in ("job_matches", "jobs"):
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS is_active")
    active_flag.drop(op.get_bind(), checkfirst=True)
